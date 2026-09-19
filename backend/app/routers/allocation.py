from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Assignment, DecisionLog, Employee, Task
from app.schemas import (
    OptimizeRequest, ReallocationResult, AssignmentChange, EmployeeUnavailableEvent,
    DecisionTraceOut, ExplanationOut, ManagerAgentRequest, ManagerAgentResponse,
)
from app.optimizer.engine import run_allocation
from app.optimizer.disruption import get_full_previous_assignment
from app.services.disruption_service import trigger_employee_unavailable
from app.services.websocket_manager import manager as ws_manager
from app.agents.graph import run_manager_agent

router = APIRouter(tags=["allocation"])


@router.post("/admin/reset-demo")
async def reset_demo(user=Depends(require_roles("ADMIN", "MANAGER"))):
    """
    Live-demo safety net: re-runs the full deterministic seed (30 employees,
    100 tasks, initial CP-SAT optimization, Priya -> T4021 guaranteed) so a
    presenter can replay the disruption scenario as many times as needed
    during judging without touching a terminal. Runs in a threadpool since
    it performs blocking DB + solver work.
    """
    from app.seed import seed as run_seed

    def _run():
        run_seed()

    await run_in_threadpool(_run)
    await ws_manager.broadcast({"type": "DEMO_RESET", "message": "Demo data reset to initial state"})
    return {"status": "reset_complete"}


@router.post("/allocation/optimize", response_model=ReallocationResult)
async def optimize_allocation(payload: OptimizeRequest, db: Session = Depends(get_db), user=Depends(require_roles("ADMIN", "MANAGER"))):
    if payload.task_ids:
        tasks = db.query(Task).filter(Task.id.in_(payload.task_ids)).all()
    else:
        tasks = db.query(Task).all()
    if not tasks:
        raise HTTPException(400, "No tasks to optimize")

    all_employees = db.query(Employee).all()
    previous_assignment = get_full_previous_assignment(db)

    result = run_allocation(
        db=db, task_scope=tasks, all_employees=all_employees, trigger="OPTIMIZE",
        previous_assignment=previous_assignment,
        weights={
            "fairness_weight": payload.fairness_weight, "sla_weight": payload.sla_weight,
            "skill_weight": payload.skill_weight, "preference_weight": payload.preference_weight,
        },
    )
    db.commit()

    changes = _decision_logs_to_changes(db, result.decision_logs)
    response = ReallocationResult(
        trigger="OPTIMIZE", changes=changes, unresolved_task_ids=result.unresolved_task_ids,
        duration_ms=result.duration_ms, solver_status=result.status, fairness_index=result.fairness_index,
    )
    await ws_manager.broadcast({
        "type": "REALLOCATION_COMPLETE", "trigger": "OPTIMIZE",
        "changes": [c.model_dump() for c in changes], "status": result.status,
        "duration_ms": result.duration_ms, "fairness_index": result.fairness_index,
    })
    return response


@router.post("/allocation/reallocate", response_model=ReallocationResult)
async def reallocate(payload: EmployeeUnavailableEvent, db: Session = Depends(get_db), user=Depends(require_roles("ADMIN", "MANAGER"))):
    """Explicit re-optimization trigger for an already-unavailable employee's tasks."""
    from app.optimizer.disruption import find_affected_tasks
    all_employees = db.query(Employee).all()
    previous_assignment = get_full_previous_assignment(db)
    affected = find_affected_tasks(db, payload.employee_id)
    if not affected:
        return ReallocationResult(trigger="DISRUPTION", changes=[], unresolved_task_ids=[], duration_ms=0.0,
                                   solver_status="NO_AFFECTED_TASKS", fairness_index=1.0)
    result = run_allocation(db=db, task_scope=affected, all_employees=all_employees, trigger="DISRUPTION",
                             previous_assignment=previous_assignment)
    db.commit()
    changes = _decision_logs_to_changes(db, result.decision_logs)
    await ws_manager.broadcast({
        "type": "REALLOCATION_COMPLETE", "trigger": "DISRUPTION", "affected_employee_id": payload.employee_id,
        "changes": [c.model_dump() for c in changes], "status": result.status,
        "duration_ms": result.duration_ms, "fairness_index": result.fairness_index,
    })
    return ReallocationResult(trigger="DISRUPTION", changes=changes, unresolved_task_ids=result.unresolved_task_ids,
                               duration_ms=result.duration_ms, solver_status=result.status, fairness_index=result.fairness_index)


@router.post("/events/employee-unavailable")
async def employee_unavailable_event(payload: EmployeeUnavailableEvent, db: Session = Depends(get_db), user=Depends(require_roles("ADMIN", "MANAGER"))):
    """
    Primary disruption-simulation entry point for the demo's
    '🚨 Simulate Employee Unavailable' button:
    Frontend -> POST event -> backend -> event bus -> reallocation workflow
    -> optimizer -> verifier -> database -> WebSocket -> frontend update.
    """
    try:
        outcome = await trigger_employee_unavailable(db, payload.employee_id, payload.reason)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return outcome


@router.get("/allocation/{task_id}")
def get_allocation(task_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    assignment = db.query(Assignment).filter(Assignment.task_id == task_id, Assignment.is_active == True).first()
    if not assignment:
        return {"task_id": task_id, "employee_id": None, "status": "UNASSIGNED"}
    emp = db.query(Employee).filter(Employee.id == assignment.employee_id).first()
    return {
        "task_id": task_id, "employee_id": assignment.employee_id,
        "employee_name": emp.name if emp else None,
        "skill_match_score": assignment.skill_match_score, "workload_score": assignment.workload_score,
        "sla_risk": assignment.sla_risk, "preference_score": assignment.preference_score,
        "travel_minutes": assignment.travel_minutes, "objective_score": assignment.objective_score,
    }


@router.get("/allocation/{task_id}/explanation", response_model=ExplanationOut)
def get_explanation(task_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    log = db.query(DecisionLog).filter(DecisionLog.task_id == task_id).order_by(DecisionLog.created_at.desc()).first()
    if not log:
        raise HTTPException(404, "No decision log for this task yet")
    return ExplanationOut(task_id=task_id, explanation=log.explanation, reason_codes=log.reason_codes)


@router.get("/allocation/{task_id}/decision-trace", response_model=DecisionTraceOut)
def get_decision_trace(task_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    log = db.query(DecisionLog).filter(DecisionLog.task_id == task_id).order_by(DecisionLog.created_at.desc()).first()
    if not log:
        raise HTTPException(404, "No decision trace for this task yet")
    return DecisionTraceOut(
        task_id=log.task_id, chosen_employee_id=log.chosen_employee_id,
        previous_employee_id=log.previous_employee_id, trigger=log.trigger,
        candidates=log.candidates, hard_constraints_checked=log.hard_constraints_checked,
        reason_codes=log.reason_codes, explanation=log.explanation,
        objective_breakdown=log.objective_breakdown, created_at=log.created_at,
    )


@router.post("/agents/manager", response_model=ManagerAgentResponse)
async def manager_agent_endpoint(payload: ManagerAgentRequest, db: Session = Depends(get_db), user=Depends(require_roles("ADMIN", "MANAGER"))):
    """AI Decision Center: natural-language instruction -> bounded LangGraph
    workflow -> structured optimizer parameters -> real CP-SAT solve."""
    state = run_manager_agent(db, payload.instruction)
    db.commit()
    result = state["result"]
    changes = _decision_logs_to_changes(db, result.decision_logs)
    await ws_manager.broadcast({
        "type": "REALLOCATION_COMPLETE", "trigger": "MANAGER_AGENT",
        "changes": [c.model_dump() for c in changes], "status": result.status,
        "duration_ms": result.duration_ms, "fairness_index": result.fairness_index,
    })
    return ManagerAgentResponse(
        interpreted_parameters=state["params"], action_taken=state["action_taken"],
        result=ReallocationResult(trigger="MANAGER_AGENT", changes=changes,
                                   unresolved_task_ids=result.unresolved_task_ids,
                                   duration_ms=result.duration_ms, solver_status=result.status,
                                   fairness_index=result.fairness_index),
    )


def _decision_logs_to_changes(db: Session, logs: List[DecisionLog]) -> List[AssignmentChange]:
    changes = []
    for log in logs:
        task = db.query(Task).filter(Task.id == log.task_id).first()
        old_emp = db.query(Employee).filter(Employee.id == log.previous_employee_id).first() if log.previous_employee_id else None
        new_emp = db.query(Employee).filter(Employee.id == log.chosen_employee_id).first() if log.chosen_employee_id else None
        chosen = next((c for c in log.candidates if c["employee_id"] == log.chosen_employee_id), None)
        changes.append(AssignmentChange(
            task_id=log.task_id, task_title=task.title if task else log.task_id,
            old_employee_id=log.previous_employee_id, old_employee_name=old_emp.name if old_emp else None,
            new_employee_id=log.chosen_employee_id, new_employee_name=new_emp.name if new_emp else None,
            skill_match=chosen["skill_match"] if chosen else 0.0,
            workload=chosen["workload_utilization_after"] if chosen else 0.0,
            sla_risk=chosen["sla_risk"] if chosen else 0.0,
            reason_codes=log.reason_codes, explanation=log.explanation,
        ))
    return changes
