"""
Deterministic tools called by the agent graph. Agents never assign
employees to tasks directly -- they call these tools, and the tools call
the real optimizer / DB / ML services.
"""
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Employee, Task, TaskStatus, TaskPriority
from app.services.fairness import jain_fairness_index, utilization_ratios

settings = get_settings()


def parse_manager_instruction(instruction: str) -> dict:
    """
    Manager Agent: converts a natural-language instruction into structured
    optimizer parameters. Uses the LLM if configured; otherwise a
    deterministic keyword parser (offline fallback -- always produces a
    valid, safe parameter set).
    """
    if settings.ANTHROPIC_API_KEY:
        llm_result = _parse_with_llm(instruction)
        if llm_result:
            return llm_result
    return _parse_with_keywords(instruction)


def _parse_with_keywords(instruction: str) -> dict:
    text = instruction.lower()
    params = {
        "priority_filter": None,
        "fairness_weight": 1.0,
        "sla_weight": 1.0,
        "skill_weight": 1.0,
        "preference_weight": 0.5,
        "scope": "unassigned",
    }
    if any(k in text for k in ["urgent", "high priority", "high-priority", "critical"]):
        params["priority_filter"] = "HIGH"
        if "critical" in text:
            params["priority_filter"] = "CRITICAL"
    if "balance" in text or "fairness" in text or "fair" in text:
        params["fairness_weight"] = 2.0
    if "sla" in text or "deadline" in text or "risk" in text:
        params["sla_weight"] = 2.0
    if "all" in text and "task" in text:
        params["scope"] = "all"
    if "unavailable" in text:
        params["scope"] = "affected_by_unavailability"
    return params


def _parse_with_llm(instruction: str) -> Optional[dict]:  # pragma: no cover - network dependent
    try:
        import httpx, json
        system_prompt = (
            "Convert the manager's natural-language allocation instruction into a JSON object "
            'with keys: priority_filter (one of null,"LOW","MEDIUM","HIGH","CRITICAL"), '
            "fairness_weight (float 0.5-3), sla_weight (float 0.5-3), skill_weight (float 0.5-3), "
            'preference_weight (float 0-1), scope (one of "all","unassigned","affected_by_unavailability"). '
            "Output ONLY the JSON object, nothing else."
        )
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.LLM_MODEL, "max_tokens": 200,
                "system": system_prompt,
                "messages": [{"role": "user", "content": instruction}],
            },
            timeout=8.0,
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"].strip()
        return json.loads(text)
    except Exception:
        return None


def skill_agent_snapshot(db: Session) -> dict:
    """Skill Intelligence Agent: reports current skill-graph coverage."""
    from app.services.skills import SKILL_GRAPH
    return {"skills_in_graph": SKILL_GRAPH.number_of_nodes(), "relationships": SKILL_GRAPH.number_of_edges()}


def workload_agent_snapshot(db: Session) -> dict:
    """Workload Agent: current fairness snapshot across all employees."""
    employees = db.query(Employee).all()
    utils = utilization_ratios([e.current_workload_hours for e in employees], [e.max_capacity_hours for e in employees])
    return {
        "fairness_index": jain_fairness_index(utils),
        "avg_utilization": round(sum(utils) / len(utils), 3) if utils else 0.0,
        "employee_count": len(employees),
    }


def sla_agent_snapshot(db: Session) -> dict:
    """SLA Risk Agent: count of tasks currently flagged AT_RISK."""
    at_risk = db.query(Task).filter(Task.status == TaskStatus.AT_RISK).count()
    total = db.query(Task).filter(Task.status != TaskStatus.COMPLETED).count()
    return {"tasks_at_risk": at_risk, "active_tasks": total}


def select_task_scope(db: Session, params: dict, explicit_task_ids: Optional[list] = None) -> list:
    query = db.query(Task).filter(Task.status != TaskStatus.COMPLETED)
    if explicit_task_ids:
        query = query.filter(Task.id.in_(explicit_task_ids))
    elif params.get("scope") == "unassigned":
        query = query.filter(Task.status.in_([TaskStatus.UNASSIGNED, TaskStatus.AT_RISK]))
    if params.get("priority_filter"):
        try:
            query = query.filter(Task.priority == TaskPriority(params["priority_filter"]))
        except ValueError:
            pass
    tasks = query.all()
    if not tasks and params.get("scope") == "unassigned":
        # nothing unassigned -> broaden to all active tasks so the manager's request still does something
        tasks = db.query(Task).filter(Task.status != TaskStatus.COMPLETED).all()
    return tasks
