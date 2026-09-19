"""
SQLAlchemy ORM models for SmartAlloc AI.

Notes on pragmatic substitutions (documented, not hidden):
- Embeddings are stored as JSON-encoded float arrays in a TEXT column rather
  than a native pgvector column, so the schema works identically on SQLite
  (zero-install local dev) and Postgres (docker-compose). Cosine similarity
  is computed in Python (app/services/skills.py). Swapping to a real
  `vector` column + pgvector `<->` operator is a drop-in upgrade path when
  running against Postgres with the pgvector extension enabled.
"""
import enum
import json
import uuid
from datetime import datetime


from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text, JSON
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------- Enums ----
class RoleEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"


class TaskStatus(str, enum.Enum):
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    AT_RISK = "AT_RISK"


class TaskPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AvailabilityStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    ON_LEAVE = "ON_LEAVE"
    PARTIALLY_AVAILABLE = "PARTIALLY_AVAILABLE"


class AlertSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EventType(str, enum.Enum):
    EMPLOYEE_UNAVAILABLE = "EMPLOYEE_UNAVAILABLE"
    EMPLOYEE_AVAILABLE = "EMPLOYEE_AVAILABLE"
    TASK_CREATED = "TASK_CREATED"
    REALLOCATION = "REALLOCATION"
    OPTIMIZATION_RUN = "OPTIMIZATION_RUN"
    SLA_BREACH_RISK = "SLA_BREACH_RISK"


# --------------------------------------------------------------- Users -----
class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: gen_id("USR"))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.EMPLOYEE)
    employee_id = Column(String, ForeignKey("employees.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ------------------------------------------------------------- Skills ------
class Skill(Base):
    __tablename__ = "skills"
    id = Column(String, primary_key=True, default=lambda: gen_id("SKL"))
    name = Column(String, unique=True, nullable=False, index=True)
    category = Column(String, nullable=True)
    embedding = Column(Text, nullable=True)  # JSON float array

    def get_embedding(self):
        return json.loads(self.embedding) if self.embedding else None

    def set_embedding(self, vec):
        self.embedding = json.dumps(vec)


class SkillRelationship(Base):
    """Skill knowledge graph edges (transferable-skill relationships)."""
    __tablename__ = "skill_relationships"
    id = Column(Integer, primary_key=True, autoincrement=True)
    skill_a_id = Column(String, ForeignKey("skills.id"), nullable=False)
    skill_b_id = Column(String, ForeignKey("skills.id"), nullable=False)
    relationship_type = Column(String, default="RELATED_TO")
    strength = Column(Float, default=0.5)  # 0..1 transferability strength


# ----------------------------------------------------------- Employees -----
class Employee(Base):
    __tablename__ = "employees"
    id = Column(String, primary_key=True, default=lambda: gen_id("EMP"))
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    role = Column(String, nullable=False)
    experience_years = Column(Float, default=1.0)
    working_hours_per_week = Column(Float, default=40.0)
    max_capacity_hours = Column(Float, default=40.0)
    current_workload_hours = Column(Float, default=0.0)
    location = Column(String, default="Remote")
    availability_status = Column(Enum(AvailabilityStatus), default=AvailabilityStatus.AVAILABLE)
    historical_performance_score = Column(Float, default=0.75)  # 0..1
    certifications = Column(JSON, default=list)
    project_experience = Column(JSON, default=list)
    embedding = Column(Text, nullable=True)  # aggregate skill-profile embedding
    created_at = Column(DateTime, default=datetime.utcnow)

    skills = relationship("EmployeeSkill", back_populates="employee", cascade="all, delete-orphan")
    preferences = relationship("EmployeePreference", back_populates="employee", cascade="all, delete-orphan")

    def get_embedding(self):
        return json.loads(self.embedding) if self.embedding else None

    def set_embedding(self, vec):
        self.embedding = json.dumps(vec)


class EmployeeSkill(Base):
    __tablename__ = "employee_skills"
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, ForeignKey("employees.id"), nullable=False)
    skill_id = Column(String, ForeignKey("skills.id"), nullable=False)
    proficiency = Column(Float, default=0.7)  # 0..1

    employee = relationship("Employee", back_populates="skills")
    skill = relationship("Skill")


class EmployeePreference(Base):
    __tablename__ = "employee_preferences"
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, ForeignKey("employees.id"), nullable=False)
    preferred_project_type = Column(String, nullable=True)
    preferred_location = Column(String, nullable=True)
    preferred_skill = Column(String, nullable=True)
    avoid_overtime = Column(Boolean, default=True)

    employee = relationship("Employee", back_populates="preferences")


class Availability(Base):
    """Time-stamped availability change log (for audit / disruption history)."""
    __tablename__ = "availability"
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, ForeignKey("employees.id"), nullable=False)
    status = Column(Enum(AvailabilityStatus), nullable=False)
    reason = Column(String, nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------- Tasks ----
class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True, default=lambda: gen_id("T"))
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM)
    estimated_hours = Column(Float, default=8.0)
    deadline = Column(DateTime, nullable=True)
    sla_hours = Column(Float, default=48.0)  # SLA window from creation
    location = Column(String, default="Remote")
    complexity = Column(Float, default=0.5)  # 0..1
    project = Column(String, default="General")
    status = Column(Enum(TaskStatus), default=TaskStatus.UNASSIGNED)
    required_certifications = Column(JSON, default=list)
    embedding = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    requirements = relationship("TaskRequirement", back_populates="task", cascade="all, delete-orphan")

    def get_embedding(self):
        return json.loads(self.embedding) if self.embedding else None

    def set_embedding(self, vec):
        self.embedding = json.dumps(vec)


class TaskRequirement(Base):
    __tablename__ = "task_requirements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    skill_id = Column(String, ForeignKey("skills.id"), nullable=False)
    min_proficiency = Column(Float, default=0.5)
    mandatory = Column(Boolean, default=True)

    task = relationship("Task", back_populates="requirements")
    skill = relationship("Skill")


# ----------------------------------------------------------- Assignments ---
class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(String, primary_key=True, default=lambda: gen_id("ASG"))
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    employee_id = Column(String, ForeignKey("employees.id"), nullable=True)
    skill_match_score = Column(Float, default=0.0)
    workload_score = Column(Float, default=0.0)
    sla_risk = Column(Float, default=0.0)
    preference_score = Column(Float, default=0.0)
    travel_minutes = Column(Float, default=0.0)
    objective_score = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TaskHistory(Base):
    """Completed-task performance log, used to train SLA/completion-time models."""
    __tablename__ = "task_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, nullable=False)
    employee_id = Column(String, nullable=False)
    actual_hours = Column(Float, nullable=False)
    was_sla_breached = Column(Boolean, default=False)
    skill_match_at_assignment = Column(Float, default=0.5)
    completed_at = Column(DateTime, default=datetime.utcnow)


class WorkloadHistory(Base):
    __tablename__ = "workload_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, ForeignKey("employees.id"), nullable=False)
    workload_hours = Column(Float, nullable=False)
    fairness_index_snapshot = Column(Float, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class AllocationEvent(Base):
    __tablename__ = "allocation_events"
    id = Column(String, primary_key=True, default=lambda: gen_id("EVT"))
    event_type = Column(Enum(EventType), nullable=False)
    payload = Column(JSON, default=dict)
    triggered_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DecisionLog(Base):
    """Full decision trace for one assignment decision -- powers 'Why this employee?'."""
    __tablename__ = "decision_logs"
    id = Column(String, primary_key=True, default=lambda: gen_id("DEC"))
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    chosen_employee_id = Column(String, nullable=True)
    previous_employee_id = Column(String, nullable=True)
    trigger = Column(String, default="OPTIMIZE")  # OPTIMIZE | DISRUPTION | MANUAL
    candidates = Column(JSON, default=list)  # list of {employee_id, scores..., rejected_reason}
    hard_constraints_checked = Column(JSON, default=list)
    reason_codes = Column(JSON, default=list)
    explanation = Column(Text, default="")
    objective_breakdown = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class SLAPrediction(Base):
    __tablename__ = "sla_predictions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    employee_id = Column(String, nullable=True)
    sla_risk_probability = Column(Float, nullable=False)
    predicted_completion_hours = Column(Float, nullable=False)
    model_version = Column(String, default="synthetic-v1")
    created_at = Column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(String, primary_key=True, default=lambda: gen_id("NOTIF"))
    severity = Column(Enum(AlertSeverity), default=AlertSeverity.LOW)
    title = Column(String, nullable=False)
    message = Column(Text, default="")
    related_task_id = Column(String, nullable=True)
    related_employee_id = Column(String, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
