from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Employee, Task, TaskStatus, Assignment, Notification, AvailabilityStatus
from app.schemas import WorkloadAnalytics, FairnessAnalytics, SLAAnalyticsItem, DashboardStats
from app.services.fairness import jain_fairness_index, gini_coefficient, workload_variance, utilization_ratios

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/workload", response_model=list[WorkloadAnalytics])
def workload_analytics(db: Session = Depends(get_db), user=Depends(get_current_user)):
    employees = db.query(Employee).all()
    return [
        WorkloadAnalytics(
            employee_id=e.id, employee_name=e.name, workload_hours=e.current_workload_hours,
            max_capacity=e.max_capacity_hours,
            utilization=round(e.current_workload_hours / e.max_capacity_hours, 3) if e.max_capacity_hours else 0.0,
        ) for e in employees
    ]


@router.get("/fairness", response_model=FairnessAnalytics)
def fairness_analytics(db: Session = Depends(get_db), user=Depends(get_current_user)):
    employees = db.query(Employee).all()
    workloads = [e.current_workload_hours for e in employees]
    capacities = [e.max_capacity_hours for e in employees]
    utils = utilization_ratios(workloads, capacities)
    per_employee = [
        WorkloadAnalytics(employee_id=e.id, employee_name=e.name, workload_hours=e.current_workload_hours,
                           max_capacity=e.max_capacity_hours, utilization=round(u, 3))
        for e, u in zip(employees, utils)
    ]
    return FairnessAnalytics(
        jain_fairness_index=jain_fairness_index(utils),
        gini_coefficient=gini_coefficient(utils),
        workload_variance=workload_variance(utils),
        per_employee=per_employee,
    )


@router.get("/sla", response_model=list[SLAAnalyticsItem])
def sla_analytics(db: Session = Depends(get_db), user=Depends(get_current_user)):
    tasks = db.query(Task).filter(Task.status != TaskStatus.COMPLETED).all()
    items = []
    for t in tasks:
        assignment = db.query(Assignment).filter(Assignment.task_id == t.id, Assignment.is_active == True).first()
        items.append(SLAAnalyticsItem(
            task_id=t.id, task_title=t.title,
            sla_risk=assignment.sla_risk if assignment else 0.5,
            predicted_completion_hours=t.estimated_hours,
            deadline=t.deadline, priority=t.priority.value if hasattr(t.priority, "value") else t.priority,
        ))
    return sorted(items, key=lambda i: i.sla_risk, reverse=True)


@router.get("/dashboard", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db), user=Depends(get_current_user)):
    employees = db.query(Employee).all()
    tasks = db.query(Task).all()
    assigned = [t for t in tasks if t.status == TaskStatus.ASSIGNED]
    unassigned = [t for t in tasks if t.status == TaskStatus.UNASSIGNED]
    available = [e for e in employees if e.availability_status == AvailabilityStatus.AVAILABLE]
    utils = utilization_ratios([e.current_workload_hours for e in employees], [e.max_capacity_hours for e in employees])

    assignments = db.query(Assignment).filter(Assignment.is_active == True).all()
    avg_sla_risk = round(sum(a.sla_risk for a in assignments) / len(assignments), 3) if assignments else 0.0
    disruptions = db.query(Employee).filter(Employee.availability_status == AvailabilityStatus.UNAVAILABLE).count()

    return DashboardStats(
        total_employees=len(employees), available_employees=len(available),
        active_tasks=len([t for t in tasks if t.status != TaskStatus.COMPLETED]),
        assigned_tasks=len(assigned), unassigned_tasks=len(unassigned),
        avg_sla_risk=avg_sla_risk,
        avg_workload_utilization=round(sum(utils) / len(utils), 3) if utils else 0.0,
        fairness_index=jain_fairness_index(utils),
        active_disruptions=disruptions,
    )


@router.get("/notifications")
def list_notifications(db: Session = Depends(get_db), user=Depends(get_current_user)):
    notifs = db.query(Notification).order_by(Notification.created_at.desc()).limit(50).all()
    return [{
        "id": n.id, "severity": n.severity.value if hasattr(n.severity, "value") else n.severity,
        "title": n.title, "message": n.message, "related_task_id": n.related_task_id,
        "related_employee_id": n.related_employee_id, "is_read": n.is_read, "created_at": n.created_at,
    } for n in notifs]
