from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Task, TaskRequirement, Skill, TaskStatus, Assignment, Employee, TaskPriority
from app.schemas import TaskCreate, TaskUpdate, TaskOut
from app.services.skills import embed_text
from app.services.sla_model import predict_sla_risk_and_completion, remaining_hours_until_deadline
from app.services.websocket_manager import manager as ws_manager
from app.services.events import publish_event

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _task_to_out(db: Session, t: Task) -> TaskOut:
    assignment = db.query(Assignment).filter(Assignment.task_id == t.id, Assignment.is_active == True).first()
    emp = db.query(Employee).filter(Employee.id == assignment.employee_id).first() if assignment else None
    return TaskOut(
        id=t.id, title=t.title, description=t.description,
        priority=t.priority.value if hasattr(t.priority, "value") else t.priority,
        estimated_hours=t.estimated_hours, deadline=t.deadline, sla_hours=t.sla_hours,
        location=t.location, complexity=t.complexity, project=t.project,
        status=t.status.value if hasattr(t.status, "value") else t.status,
        required_skills=[r.skill.name for r in t.requirements],
        assigned_employee_id=emp.id if emp else None,
        assigned_employee_name=emp.name if emp else None,
        skill_match_score=assignment.skill_match_score if assignment else None,
        sla_risk=assignment.sla_risk if assignment else None,
    )


@router.get("", response_model=List[TaskOut])
def list_tasks(
    status_filter: Optional[str] = None, priority: Optional[str] = None,
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    q = db.query(Task).options(joinedload(Task.requirements).joinedload(TaskRequirement.skill))
    if status_filter:
        q = q.filter(Task.status == TaskStatus(status_filter))
    if priority:
        q = q.filter(Task.priority == TaskPriority(priority))
    return [_task_to_out(db, t) for t in q.order_by(Task.created_at.desc()).all()]


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t:
        raise HTTPException(404, "Task not found")
    return _task_to_out(db, t)


@router.post("", response_model=TaskOut)
async def create_task(payload: TaskCreate, db: Session = Depends(get_db), user=Depends(require_roles("ADMIN", "MANAGER"))):
    task = Task(
        title=payload.title, description=payload.description, priority=TaskPriority(payload.priority),
        estimated_hours=payload.estimated_hours, deadline=payload.deadline, sla_hours=payload.sla_hours,
        location=payload.location, complexity=payload.complexity, project=payload.project,
        required_certifications=payload.required_certifications,
    )
    task.set_embedding(embed_text(f"{payload.title} {payload.description}"))
    db.add(task)
    db.flush()

    for req in payload.required_skills:
        skill = db.query(Skill).filter(Skill.name.ilike(req.skill_name)).first()
        if not skill:
            skill = Skill(name=req.skill_name)
            skill.set_embedding(embed_text(req.skill_name))
            db.add(skill)
            db.flush()
        db.add(TaskRequirement(task_id=task.id, skill_id=skill.id, min_proficiency=req.min_proficiency, mandatory=req.mandatory))

    db.commit()
    db.refresh(task)

    await publish_event("TASK_CREATED", {"task_id": task.id, "title": task.title})
    await ws_manager.broadcast({"type": "TASK_CREATED", "task_id": task.id, "title": task.title, "priority": task.priority.value})

    return _task_to_out(db, task)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(task_id: str, payload: TaskUpdate, db: Session = Depends(get_db), user=Depends(require_roles("ADMIN", "MANAGER"))):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    data = payload.model_dump(exclude_unset=True)
    if "priority" in data and data["priority"]:
        data["priority"] = TaskPriority(data["priority"])
    if "status" in data and data["status"]:
        data["status"] = TaskStatus(data["status"])
    for field, value in data.items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return _task_to_out(db, task)
