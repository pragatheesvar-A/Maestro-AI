"""
Explanation Agent.

Receives ONLY trusted structured decision data (reason codes + numeric
scores already computed by the deterministic optimizer/solution verifier)
and turns it into a short, factual, human-readable sentence. It never
invents facts: every clause in the generated text traces back to a field
in the input dict.

If ANTHROPIC_API_KEY is configured, we ask the LLM to *rephrase* the same
structured facts more fluently -- with a strict system prompt forbidding it
from adding any fact not present in the JSON it is given. If no key is
configured (or the call fails), the deterministic template below is used,
which is itself a fully valid, factual explanation (this is the offline
fallback required by the spec).
"""
import json
import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger("smartalloc.explanation")
settings = get_settings()

REASON_TEXT = {
    "EMPLOYEE_UNAVAILABLE": "the previously assigned employee became unavailable",
    "ASSIGNMENT_UNCHANGED_MINIMIZES_DISRUPTION": "keeping the existing assignment minimizes disruption",
    "REASSIGNED_MINIMUM_DISRUPTION_CANDIDATE": "this candidate required the least disruption to the existing schedule",
    "NO_FEASIBLE_CANDIDATE": "no employee currently satisfies the hard constraints for this task",
    "HIGH_SKILL_MATCH": "a high skill compatibility",
    "ADEQUATE_SKILL_MATCH": "an adequate skill compatibility",
    "SUFFICIENT_CAPACITY": "sufficient remaining capacity",
    "LOW_SLA_RISK": "low SLA risk",
    "ELEVATED_SLA_RISK": "elevated SLA risk that should be monitored",
    "MATCHES_PREFERENCE": "alignment with the employee's stated preferences",
    "IMPROVES_FAIRNESS": "a workload-balanced (fair) choice",
    "GRACEFUL_DEGRADATION_TRANSFERABLE_SKILL": "a related, transferable skill rather than an exact match",
    "HIGH_EMPLOYEE_ACCEPTANCE_LIKELIHOOD": "a high likelihood the employee will accept this assignment",
    "LOW_EMPLOYEE_ACCEPTANCE_RISK": "a risk the employee may push back on this assignment",
}


def _deterministic_explanation(task_id, task_title, old_employee_name, new_employee_name, reason_codes, chosen_trace) -> str:
    if new_employee_name is None:
        return (f"Task {task_id} ({task_title}) could not be assigned: "
                f"no available employee currently satisfies the required skills, capacity, and certifications.")

    clauses = [REASON_TEXT.get(c) for c in reason_codes if c in REASON_TEXT and c not in (
        "ASSIGNMENT_UNCHANGED_MINIMIZES_DISRUPTION", "REASSIGNED_MINIMUM_DISRUPTION_CANDIDATE", "EMPLOYEE_UNAVAILABLE",
        "HIGH_SKILL_MATCH", "ADEQUATE_SKILL_MATCH")]  # skill match is already stated separately via `pct` below
    clause_text = ", ".join(clauses) if clauses else "the optimizer's multi-objective evaluation"

    pct = f"{round(chosen_trace['skill_match'] * 100)}%" if chosen_trace else "an evaluated"

    if old_employee_name and old_employee_name != new_employee_name:
        reason_prefix = f"{old_employee_name} became unavailable, so " if "EMPLOYEE_UNAVAILABLE" in reason_codes else ""
        return (
            f"{new_employee_name} was selected for {task_title} because {reason_prefix}"
            f"{new_employee_name} has {pct} skill compatibility, {clause_text}, "
            f"and the reassignment minimizes disruption to the existing schedule."
        )
    return (
        f"{new_employee_name} was assigned to {task_title} based on {pct} skill compatibility, {clause_text}."
    )


def _llm_explanation(structured_facts: dict) -> Optional[str]:  # pragma: no cover - network dependent
    if not settings.ANTHROPIC_API_KEY:
        return None
    try:
        import httpx
        system_prompt = (
            "You rewrite structured task-assignment decision data into one short, "
            "factual sentence for a manager dashboard. You MUST NOT introduce any "
            "fact, number, name, or reason that is not present in the JSON provided. "
            "Do not speculate. Output plain text, one or two sentences, no markdown."
        )
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.LLM_MODEL,
                "max_tokens": 200,
                "system": system_prompt,
                "messages": [{"role": "user", "content": json.dumps(structured_facts)}],
            },
            timeout=8.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"].strip()
    except Exception as e:
        logger.warning("LLM explanation call failed, using deterministic fallback: %s", e)
        return None


def generate_explanation(task_id, task_title, old_employee_name, new_employee_name, reason_codes, chosen_trace) -> str:
    structured_facts = {
        "task_id": task_id, "task_title": task_title,
        "old_employee": old_employee_name, "new_employee": new_employee_name,
        "reason_codes": reason_codes,
        "skill_match": chosen_trace.get("skill_match") if chosen_trace else None,
        "sla_risk": chosen_trace.get("sla_risk") if chosen_trace else None,
        "workload_utilization_after": chosen_trace.get("workload_utilization_after") if chosen_trace else None,
        "travel_minutes": chosen_trace.get("travel_minutes") if chosen_trace else None,
    }
    llm_text = _llm_explanation(structured_facts)
    if llm_text:
        return llm_text
    return _deterministic_explanation(task_id, task_title, old_employee_name, new_employee_name, reason_codes, chosen_trace)
