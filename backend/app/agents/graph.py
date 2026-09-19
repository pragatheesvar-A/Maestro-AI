"""
Bounded LangGraph workflow -- the "Manager Agent" orchestration.

Manager Agent -> Skill Agent -> Workload Agent -> SLA Agent
              -> Optimization Tool (CP-SAT, deterministic)
              -> Verification Tool (deterministic)
              -> Explanation Agent
              -> END

No cycles, no unbounded autonomous loops: this is a single linear pass
through a fixed set of nodes, each calling a deterministic tool. The LLM
(if configured) is only used inside `parse_manager_instruction` (to turn
free text into structured parameters) and inside the Explanation Agent (to
rephrase already-computed structured facts) -- never to pick an employee.
"""
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

from app.agents.tools import (
    parse_manager_instruction, skill_agent_snapshot, workload_agent_snapshot,
    sla_agent_snapshot, select_task_scope,
)
from app.optimizer.engine import run_allocation, AllocationRunResult
from app.optimizer.disruption import get_full_previous_assignment
from app.models import Employee


class ManagerState(TypedDict, total=False):
    db: Session
    instruction: str
    explicit_task_ids: Optional[List[str]]
    params: Dict[str, Any]
    skill_snapshot: Dict[str, Any]
    workload_snapshot: Dict[str, Any]
    sla_snapshot: Dict[str, Any]
    task_scope: list
    result: AllocationRunResult
    action_taken: str


def node_manager_parse(state: ManagerState) -> ManagerState:
    params = parse_manager_instruction(state["instruction"])
    state["params"] = params
    return state


def node_skill_agent(state: ManagerState) -> ManagerState:
    state["skill_snapshot"] = skill_agent_snapshot(state["db"])
    return state


def node_workload_agent(state: ManagerState) -> ManagerState:
    state["workload_snapshot"] = workload_agent_snapshot(state["db"])
    return state


def node_sla_agent(state: ManagerState) -> ManagerState:
    state["sla_snapshot"] = sla_agent_snapshot(state["db"])
    return state


def node_optimization(state: ManagerState) -> ManagerState:
    db = state["db"]
    task_scope = select_task_scope(db, state["params"], state.get("explicit_task_ids"))
    state["task_scope"] = task_scope
    all_employees = db.query(Employee).all()
    previous_assignment = get_full_previous_assignment(db)
    weights = {
        "fairness_weight": state["params"].get("fairness_weight", 1.0),
        "sla_weight": state["params"].get("sla_weight", 1.0),
        "skill_weight": state["params"].get("skill_weight", 1.0),
        "preference_weight": state["params"].get("preference_weight", 0.5),
    }
    result = run_allocation(
        db=db, task_scope=task_scope, all_employees=all_employees,
        trigger="MANAGER_AGENT", previous_assignment=previous_assignment, weights=weights,
    )
    state["result"] = result
    return state


def node_verification(state: ManagerState) -> ManagerState:
    # engine.run_allocation already ran the solution verifier internally
    # (hard-constraint re-check) before returning; this node records that
    # the pipeline passed verification for the decision trace / API response.
    state["action_taken"] = f"optimized {len(state.get('task_scope', []))} task(s); status={state['result'].status}"
    return state


def node_explanation(state: ManagerState) -> ManagerState:
    # Explanations were already generated per-assignment inside
    # run_allocation via the Explanation Agent (app/agents/explanation.py).
    return state


def build_manager_graph():
    graph = StateGraph(ManagerState)
    graph.add_node("manager_parse", node_manager_parse)
    graph.add_node("skill_agent", node_skill_agent)
    graph.add_node("workload_agent", node_workload_agent)
    graph.add_node("sla_agent", node_sla_agent)
    graph.add_node("optimization", node_optimization)
    graph.add_node("verification", node_verification)
    graph.add_node("explanation", node_explanation)

    graph.set_entry_point("manager_parse")
    graph.add_edge("manager_parse", "skill_agent")
    graph.add_edge("skill_agent", "workload_agent")
    graph.add_edge("workload_agent", "sla_agent")
    graph.add_edge("sla_agent", "optimization")
    graph.add_edge("optimization", "verification")
    graph.add_edge("verification", "explanation")
    graph.add_edge("explanation", END)
    return graph.compile()


_compiled_graph = None


def get_manager_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_manager_graph()
    return _compiled_graph


def run_manager_agent(db: Session, instruction: str, explicit_task_ids: Optional[List[str]] = None) -> ManagerState:
    graph = get_manager_graph()
    initial: ManagerState = {"db": db, "instruction": instruction, "explicit_task_ids": explicit_task_ids}
    final_state = graph.invoke(initial)
    return final_state
