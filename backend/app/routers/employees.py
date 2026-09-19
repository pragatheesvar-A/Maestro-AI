from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Employee, EmployeeSkill, Skill, AvailabilityStatus
from app.schemas import EmployeeCreate, EmployeeUpdate, EmployeeOut, AvailabilityUpdate
from app.services.skills import embed_text, build_skill_graph
from app.services.websocket_manager import manager as ws_manager
from app.optimizer.disruption import mark_employee_available
from app.services.events import publish_event
from app.services.disruption_service import trigger_employee_unavailable
from app.services.risk_intelligence import compute_dynamic_performance, compute_unavailability_risk

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("", response_model=List[EmployeeOut])
def list_employees(
    availability: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    q = db.query(Employee).options(joinedload(Employee.skills).joinedload(EmployeeSkill.skill))
    if availability:
        q = q.filter(Employee.availability_status == AvailabilityStatus(availability))
    return [
        EmployeeOut.from_orm_full(e, performance=compute_dynamic_performance(db, e), risk=compute_unavailability_risk(db, e))
        for e in q.all()
    ]


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    emp = db.query(Employee).options(joinedload(Employee.skills).joinedload(EmployeeSkill.skill)).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(404, "Employee not found")
    return EmployeeOut.from_orm_full(emp, performance=compute_dynamic_performance(db, emp), risk=compute_unavailability_risk(db, emp))


@router.post("", response_model=EmployeeOut)
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db), user=Depends(require_roles("ADMIN", "MANAGER"))):
    emp = Employee(
        name=payload.name, email=payload.email, role=payload.role,
        experience_years=payload.experience_years,
        working_hours_per_week=payload.working_hours_per_week,
        max_capacity_hours=payload.max_capacity_hours,
        location=payload.location, certifications=payload.certifications,
    )
    emp.set_embedding(embed_text(f"{payload.role} " + " ".join(s.skill_name for s in payload.skills)))
    db.add(emp)
    db.flush()

    for s in payload.skills:
        skill = db.query(Skill).filter(Skill.name.ilike(s.skill_name)).first()
        if not skill:
            skill = Skill(name=s.skill_name)
            skill.set_embedding(embed_text(s.skill_name))
            db.add(skill)
            db.flush()
        db.add(EmployeeSkill(employee_id=emp.id, skill_id=skill.id, proficiency=s.proficiency))

    db.commit()
    build_skill_graph([s.name for s in db.query(Skill).all()])
    db.refresh(emp)
    return EmployeeOut.from_orm_full(emp)


@router.patch("/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: str, payload: EmployeeUpdate, db: Session = Depends(get_db), user=Depends(require_roles("ADMIN", "MANAGER"))):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(404, "Employee not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(emp, field, value)
    db.commit()
    db.refresh(emp)
    return EmployeeOut.from_orm_full(emp)


@router.patch("/{employee_id}/availability")
async def update_availability(employee_id: str, payload: AvailabilityUpdate, db: Session = Depends(get_db), user=Depends(require_roles("ADMIN", "MANAGER"))):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(404, "Employee not found")

    response = {"employee_id": employee_id, "new_status": payload.status, "reallocation": None}

    if payload.status == "UNAVAILABLE":
        outcome = await trigger_employee_unavailable(db, employee_id, payload.reason or "Marked unavailable")
        response["reallocation"] = outcome["changes"]
        response["fairness_index"] = outcome["fairness_index"]
        response["unresolved_task_ids"] = outcome["unresolved_task_ids"]
    else:
        emp.availability_status = AvailabilityStatus(payload.status)
        db.commit()
        await publish_event("EMPLOYEE_AVAILABLE", {"employee_id": employee_id})
        await ws_manager.broadcast({"type": "EMPLOYEE_AVAILABLE", "employee_id": employee_id, "employee_name": emp.name})

    return response
