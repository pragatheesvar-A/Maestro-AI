from datetime import datetime
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, EmailStr, ConfigDict


# --------------------------------------------------------------- Auth ------
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    user_id: str
    employee_id: Optional[str] = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: str
    role: str
    employee_id: Optional[str] = None


# ---------------------------------------------------------------- Skills ---
class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    category: Optional[str] = None


class EmployeeSkillIn(BaseModel):
    skill_name: str
    proficiency: float = 0.7


class EmployeeSkillOut(BaseModel):
    skill_name: str
    proficiency: float


# ------------------------------------------------------------- Employees ---
class EmployeeCreate(BaseModel):
    name: str
    email: str
    role: str
    experience_years: float = 1.0
    working_hours_per_week: float = 40.0
    max_capacity_hours: float = 40.0
    location: str = "Remote"
    certifications: List[str] = []
    skills: List[EmployeeSkillIn] = []


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    experience_years: Optional[float] = None
    max_capacity_hours: Optional[float] = None
    location: Optional[str] = None


class AvailabilityUpdate(BaseModel):
    status: str  # AVAILABLE | UNAVAILABLE | ON_LEAVE | PARTIALLY_AVAILABLE
    reason: Optional[str] = None
    trigger_reallocation: bool = True


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: str
    role: str
    experience_years: float
    max_capacity_hours: float
    current_workload_hours: float
    location: str
    availability_status: str
    historical_performance_score: float
    certifications: List[str] = []
    skills: List[EmployeeSkillOut] = []
    # Recency-weighted, evidence-based performance (vs. the static field
    # above) and an anticipatory unavailability-risk heuristic -- both
    # optional so this schema still works anywhere the enrichment queries
    # are skipped for performance.
    dynamic_performance_score: Optional[float] = None
    performance_trend: Optional[str] = None
    performance_sample_size: Optional[int] = None
    unavailability_risk: Optional[float] = None
    unavailability_risk_tier: Optional[str] = None

    @staticmethod
    def from_orm_full(emp, performance: Optional[Dict[str, Any]] = None, risk: Optional[Dict[str, Any]] = None) -> "EmployeeOut":
        return EmployeeOut(
            id=emp.id, name=emp.name, email=emp.email, role=emp.role,
            experience_years=emp.experience_years, max_capacity_hours=emp.max_capacity_hours,
            current_workload_hours=emp.current_workload_hours, location=emp.location,
            availability_status=emp.availability_status.value if hasattr(emp.availability_status, "value") else emp.availability_status,
            historical_performance_score=emp.historical_performance_score,
            certifications=emp.certifications or [],
            skills=[EmployeeSkillOut(skill_name=es.skill.name, proficiency=es.proficiency) for es in emp.skills],
            dynamic_performance_score=performance["score"] if performance else None,
            performance_trend=performance["trend"] if performance else None,
            performance_sample_size=performance["sample_size"] if performance else None,
            unavailability_risk=risk["risk"] if risk else None,
            unavailability_risk_tier=risk["tier"] if risk else None,
        )


# ----------------------------------------------------------------- Tasks ---
class TaskRequirementIn(BaseModel):
    skill_name: str
    min_proficiency: float = 0.5
    mandatory: bool = True


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    priority: str = "MEDIUM"
    estimated_hours: float = 8.0
    deadline: Optional[datetime] = None
    sla_hours: float = 48.0
    location: str = "Remote"
    complexity: float = 0.5
    project: str = "General"
    required_certifications: List[str] = []
    required_skills: List[TaskRequirementIn] = []


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    estimated_hours: Optional[float] = None
    deadline: Optional[datetime] = None


class TaskOut(BaseModel):
    id: str
    title: str
    description: str
    priority: str
    estimated_hours: float
    deadline: Optional[datetime]
    sla_hours: float
    location: str
    complexity: float
    project: str
    status: str
    required_skills: List[str] = []
    assigned_employee_id: Optional[str] = None
    assigned_employee_name: Optional[str] = None
    skill_match_score: Optional[float] = None
    sla_risk: Optional[float] = None


# -------------------------------------------------------------- Allocation -
class OptimizeRequest(BaseModel):
    task_ids: Optional[List[str]] = None  # None = optimize all unassigned/all tasks
    fairness_weight: float = 1.0
    sla_weight: float = 1.0
    skill_weight: float = 1.0
    preference_weight: float = 0.5
    natural_language_goal: Optional[str] = None


class EmployeeUnavailableEvent(BaseModel):
    employee_id: str
    reason: str = "Marked unavailable by manager"


class AssignmentChange(BaseModel):
    task_id: str
    task_title: str
    old_employee_id: Optional[str]
    old_employee_name: Optional[str]
    new_employee_id: Optional[str]
    new_employee_name: Optional[str]
    skill_match: float
    workload: float
    sla_risk: float
    reason_codes: List[str]
    explanation: str


class ReallocationResult(BaseModel):
    trigger: str
    affected_employee_id: Optional[str] = None
    changes: List[AssignmentChange]
    unresolved_task_ids: List[str] = []
    duration_ms: float
    solver_status: str
    fairness_index: float


class DecisionTraceOut(BaseModel):
    task_id: str
    chosen_employee_id: Optional[str]
    previous_employee_id: Optional[str]
    trigger: str
    candidates: List[Dict[str, Any]]
    hard_constraints_checked: List[str]
    reason_codes: List[str]
    explanation: str
    objective_breakdown: Dict[str, Any]
    created_at: datetime


class ExplanationOut(BaseModel):
    task_id: str
    explanation: str
    reason_codes: List[str]


# -------------------------------------------------------------- Analytics --
class WorkloadAnalytics(BaseModel):
    employee_id: str
    employee_name: str
    workload_hours: float
    max_capacity: float
    utilization: float


class FairnessAnalytics(BaseModel):
    jain_fairness_index: float
    gini_coefficient: float
    workload_variance: float
    per_employee: List[WorkloadAnalytics]


class SLAAnalyticsItem(BaseModel):
    task_id: str
    task_title: str
    sla_risk: float
    predicted_completion_hours: float
    deadline: Optional[datetime]
    priority: str


class DashboardStats(BaseModel):
    total_employees: int
    available_employees: int
    active_tasks: int
    assigned_tasks: int
    unassigned_tasks: int
    avg_sla_risk: float
    avg_workload_utilization: float
    fairness_index: float
    active_disruptions: int


class ManagerAgentRequest(BaseModel):
    instruction: str


class ManagerAgentResponse(BaseModel):
    interpreted_parameters: Dict[str, Any]
    action_taken: str
    result: Optional[ReallocationResult] = None
