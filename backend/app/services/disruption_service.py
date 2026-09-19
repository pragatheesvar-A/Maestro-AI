"""Shared disruption-trigger flow used by both PATCH /employees/{id}/availability
and POST /events/employee-unavailable (both are valid entry points per spec)."""
from sqlalchemy.orm import Session

from app.models import Employee, Task
from app.optimizer.disruption import mark_employee_unavailable, reallocate_for_disruption
from app.services.events import publish_event
from app.services.websocket_manager import manager as ws_manager


def _build_changes_payload(db: Session, result):
    changes = []
    for log in result.decision_logs:
        task = db.query(Task).filter(Task.id == log.task_id).first()
        old_emp = db.query(Employee).filter(Employee.id == log.previous_employee_id).first() if log.previous_employee_id else None
        new_emp = db.query(Employee).filter(Employee.id == log.chosen_employee_id).first() if log.chosen_employee_id else None
        changes.append({
            "task_id": log.task_id,
            "task_title": task.title if task else log.task_id,
            "old_employee_id": log.previous_employee_id,
            "old_employee_name": old_emp.name if old_emp else None,
            "new_employee_id": log.chosen_employee_id,
            "new_employee_name": new_emp.name if new_emp else None,
            "reason_codes": log.reason_codes,
            "explanation": log.explanation,
        })
    return changes


async def trigger_employee_unavailable(db: Session, employee_id: str, reason: str) -> dict:
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if emp is None:
        raise ValueError(f"Employee {employee_id} not found")

    mark_employee_unavailable(db, employee_id, reason)
    db.commit()
    await publish_event("EMPLOYEE_UNAVAILABLE", {"employee_id": employee_id, "reason": reason})
    await ws_manager.broadcast({"type": "EMPLOYEE_UNAVAILABLE", "employee_id": employee_id, "employee_name": emp.name, "reason": reason})

    result = reallocate_for_disruption(db, employee_id, reason)
    db.commit()
    changes = _build_changes_payload(db, result)

    await ws_manager.broadcast({
        "type": "REALLOCATION_COMPLETE", "trigger": "DISRUPTION",
        "affected_employee_id": employee_id, "affected_employee_name": emp.name,
        "changes": changes, "status": result.status,
        "unresolved_task_ids": result.unresolved_task_ids,
        "duration_ms": result.duration_ms, "fairness_index": result.fairness_index,
    })

    return {
        "employee_id": employee_id, "employee_name": emp.name,
        "changes": changes, "status": result.status,
        "unresolved_task_ids": result.unresolved_task_ids,
        "duration_ms": result.duration_ms, "fairness_index": result.fairness_index,
    }
