"""
Candidate generation funnel.

Per spec: never send every employee straight to OR-Tools. We apply hard
constraint filtering first, then rank remaining candidates by semantic
skill compatibility (vector similarity + skill-graph lookup) and keep only
the Top-K, which is what actually reaches the solver. This bounds solver
size and keeps the pipeline fast even as the employee pool grows.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from app.services.skills import skill_compatibility, skill_compatibility_detailed


@dataclass
class EmployeeSnapshot:
    id: str
    name: str
    availability_status: str
    max_capacity_hours: float
    current_workload_hours: float
    location: str
    certifications: List[str]
    skill_names: List[str]
    experience_years: float
    historical_performance_score: float
    preferred_project_type: Optional[str] = None
    preferred_location: Optional[str] = None
    preferred_skill: Optional[str] = None


@dataclass
class TaskSnapshot:
    id: str
    title: str
    priority: str
    estimated_hours: float
    location: str
    complexity: float
    project: str
    required_skills: List[str]
    required_certifications: List[str]
    sla_hours: float
    deadline: object = None


@dataclass
class Candidate:
    employee: EmployeeSnapshot
    skill_match: float
    hard_constraints_passed: List[str] = field(default_factory=list)
    # Per-required-skill breakdown of HOW the match was found (exact vs.
    # transferable-via-skill-graph/embedding vs. none) -- proves graceful
    # degradation under a missing exact skill rather than just asserting it.
    skill_breakdown: List[dict] = field(default_factory=list)


def hard_filter(task: TaskSnapshot, employees: List[EmployeeSnapshot]) -> List[EmployeeSnapshot]:
    """Availability, capacity headroom, mandatory certifications."""
    passed = []
    for e in employees:
        if e.availability_status != "AVAILABLE":
            continue
        headroom = e.max_capacity_hours - e.current_workload_hours
        if headroom < task.estimated_hours * 0.5:  # must have at least half the task's hours free
            continue
        if task.required_certifications:
            if not set(task.required_certifications).issubset(set(e.certifications or [])):
                continue
        passed.append(e)
    return passed


def rank_by_skill_and_topk(task: TaskSnapshot, employees: List[EmployeeSnapshot], top_k: int) -> List[Candidate]:
    scored: List[Candidate] = []
    for e in employees:
        if task.required_skills:
            breakdown = [skill_compatibility_detailed(e.skill_names, req) for req in task.required_skills]
            skill_match = sum(b["score"] for b in breakdown) / len(breakdown)
        else:
            breakdown = []
            skill_match = 0.6
        scored.append(Candidate(
            employee=e,
            skill_match=round(skill_match, 4),
            hard_constraints_passed=["AVAILABILITY", "CAPACITY", "CERTIFICATION"],
            skill_breakdown=breakdown,
        ))
    scored.sort(key=lambda c: c.skill_match, reverse=True)
    return scored[:top_k]


def generate_candidates(task: TaskSnapshot, employees: List[EmployeeSnapshot], top_k: int = 20) -> List[Candidate]:
    filtered = hard_filter(task, employees)
    return rank_by_skill_and_topk(task, filtered, top_k)
