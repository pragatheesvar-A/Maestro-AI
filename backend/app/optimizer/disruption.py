"""
Minimum-disruption reallocation.

When an employee becomes unavailable:
  1. Identify affected tasks (active assignments belonging to that employee).
  2. Freeze every other assignment -- only the affected tasks enter the
     solver batch, so unrelated employees/tasks are never touched.
  3. Generate replacement candidates from the remaining available pool.
  4. Re-optimize just the affected region (via engine.run_allocation),
     which also carries a reassignment-cost penalty in the objective so the
     solver prefers keeping continuity elsewhere and only changes what it
     must.
  5. The solution verifier (engine._verify_solution) re-checks all hard
     constraints on the output before anything is persisted / broadcast.
"""
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models import Assignment, Employee, AvailabilityStatus, Task, TaskStatus, Availability
from app.optimizer.engine import run_allocation, AllocationRunResult


def get_full_previous_assignment(db: Session) -> Dict[str, str]:
    active = db.query(Assignment).filter(Assignment.is_active == True).all()
    return {a.task_id: a.employee_id for a in active}


def find_affected_tasks(db: Session, employee_id: str) -> List[Task]:
    active_assignments = db.query(Assignment).filter(
        Assignment.employee_id == employee_id, Assignment.is_active == True
    ).all()
    task_ids = [a.task_id for a in active_assignments]
    if not task_ids:
        return []
    return db.query(Task).filter(Task.id.in_(task_ids), Task.status != TaskStatus.COMPLETED).all()


def mark_employee_unavailable(db: Session, employee_id: str, reason: str) -> Employee:
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if emp is None:
        raise ValueError(f"Employee {employee_id} not found")
    emp.availability_status = AvailabilityStatus.UNAVAILABLE
    db.add(Availability(employee_id=employee_id, status=AvailabilityStatus.UNAVAILABLE, reason=reason))
    db.flush()
    return emp


def mark_employee_available(db: Session, employee_id: str, reason: str = "Restored") -> Employee:
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if emp is None:
        raise ValueError(f"Employee {employee_id} not found")
    emp.availability_status = AvailabilityStatus.AVAILABLE
    db.add(Availability(employee_id=employee_id, status=AvailabilityStatus.AVAILABLE, reason=reason))
    db.flush()
    return emp


def reallocate_for_disruption(db: Session, employee_id: str, reason: str) -> AllocationRunResult:
    affected_tasks = find_affected_tasks(db, employee_id)
    all_employees = db.query(Employee).all()
    full_previous = get_full_previous_assignment(db)

    if not affected_tasks:
        result = AllocationRunResult()
        result.status = "NO_AFFECTED_TASKS"
        return result

    result = run_allocation(
        db=db,
        task_scope=affected_tasks,
        all_employees=all_employees,
        trigger="DISRUPTION",
        previous_assignment=full_previous,
    )
    return result
