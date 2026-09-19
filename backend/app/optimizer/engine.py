"""
Orchestration layer bridging SQLAlchemy models <-> the OR-Tools solver.

This is the single place that:
  1. builds EmployeeSnapshot/TaskSnapshot from the DB,
  2. runs the candidate-generation funnel,
  3. scores each (task, candidate) pair (skill, SLA risk, fairness,
     preference, travel, continuity),
  4. calls the CP-SAT solver,
  5. persists Assignment + DecisionLog rows,
  6. returns a structured result the API layer serializes.

Used by both POST /allocation/optimize (full/partial optimize) and the
minimum-disruption reallocation path -- they differ only in which tasks are
included in the solve batch and what "previous_assignment" freezes.
"""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import (
    Assignment, DecisionLog, Employee, EmployeePreference, EventType,
    Task, TaskStatus, AllocationEvent,
)
from app.optimizer.candidates import EmployeeSnapshot, TaskSnapshot, generate_candidates
from app.optimizer.solver import AssignmentOption, solve
from app.services.fairness import fairness_penalty_for_candidate, utilization_ratios, jain_fairness_index
from app.services.sla_model import predict_sla_risk_and_completion, remaining_hours_until_deadline


def _employee_snapshot(e: Employee) -> EmployeeSnapshot:
    pref = e.preferences[0] if e.preferences else None
    return EmployeeSnapshot(
        id=e.id, name=e.name,
        availability_status=e.availability_status.value if hasattr(e.availability_status, "value") else e.availability_status,
        max_capacity_hours=e.max_capacity_hours,
        current_workload_hours=e.current_workload_hours,
        location=e.location,
        certifications=e.certifications or [],
        skill_names=[es.skill.name for es in e.skills],
        experience_years=e.experience_years,
        historical_performance_score=e.historical_performance_score,
        preferred_project_type=pref.preferred_project_type if pref else None,
        preferred_location=pref.preferred_location if pref else None,
        preferred_skill=pref.preferred_skill if pref else None,
    )


def _task_snapshot(t: Task) -> TaskSnapshot:
    return TaskSnapshot(
        id=t.id, title=t.title,
        priority=t.priority.value if hasattr(t.priority, "value") else t.priority,
        estimated_hours=t.estimated_hours, location=t.location, complexity=t.complexity,
        project=t.project, required_skills=[r.skill.name for r in t.requirements],
        required_certifications=t.required_certifications or [], sla_hours=t.sla_hours,
        deadline=t.deadline,
    )


def _preference_score(emp: EmployeeSnapshot, task: TaskSnapshot) -> float:
    score = 0.5
    if emp.preferred_project_type and emp.preferred_project_type.lower() == task.project.lower():
        score += 0.25
    if emp.preferred_location and emp.preferred_location.lower() == task.location.lower():
        score += 0.15
    if emp.preferred_skill and emp.preferred_skill.lower() in [s.lower() for s in task.required_skills]:
        score += 0.1
    return min(1.0, score)


def _travel_minutes(emp: EmployeeSnapshot, task: TaskSnapshot) -> float:
    if emp.location.lower() == task.location.lower() or task.location.lower() == "remote" or emp.location.lower() == "remote":
        return 0.0
    return 45.0  # flat cross-location travel estimate for the MVP


class AllocationRunResult:
    def __init__(self):
        self.assignment: Dict[str, Optional[str]] = {}
        self.status: str = "UNKNOWN"
        self.unresolved_task_ids: List[str] = []
        self.decision_logs: List[DecisionLog] = []
        self.duration_ms: float = 0.0
        self.fairness_index: float = 1.0


def run_allocation(
    db: Session,
    task_scope: List[Task],
    all_employees: List[Employee],
    trigger: str,
    previous_assignment: Optional[Dict[str, str]] = None,
    weights: Optional[dict] = None,
    top_k: int = 20,
) -> AllocationRunResult:
    start = datetime.utcnow()
    weights = weights or {}
    previous_assignment = previous_assignment or {}

    task_snapshots = {t.id: _task_snapshot(t) for t in task_scope}
    emp_snapshots = {e.id: _employee_snapshot(e) for e in all_employees}

    # headroom = capacity - (current workload minus hours already tied up by
    # tasks *in this batch* that are currently assigned to this employee).
    # This frees exactly the capacity being re-decided without double counting.
    in_scope_hours_by_employee: Dict[str, float] = {}
    for t in task_scope:
        prev_emp = previous_assignment.get(t.id)
        if prev_emp:
            in_scope_hours_by_employee[prev_emp] = in_scope_hours_by_employee.get(prev_emp, 0.0) + t.estimated_hours

    employee_headroom = {}
    for eid, snap in emp_snapshots.items():
        reserved = in_scope_hours_by_employee.get(eid, 0.0)
        employee_headroom[eid] = max(0.0, snap.max_capacity_hours - (snap.current_workload_hours - reserved))

    utilizations = [
        (snap.current_workload_hours / snap.max_capacity_hours if snap.max_capacity_hours else 0.0)
        for snap in emp_snapshots.values()
    ]
    mean_utilization = sum(utilizations) / len(utilizations) if utilizations else 0.0

    all_options: List[AssignmentOption] = []
    candidate_trace: Dict[str, list] = {}  # task_id -> list of candidate score dicts (for decision trace)

    for tid, tsnap in task_snapshots.items():
        candidates = generate_candidates(tsnap, list(emp_snapshots.values()), top_k=top_k)
        # always include the currently-assigned employee as a candidate (if still available)
        # so "no unnecessary reassignment" can be evaluated fairly.
        prev_emp_id = previous_assignment.get(tid)
        if prev_emp_id and prev_emp_id in emp_snapshots and not any(c.employee.id == prev_emp_id for c in candidates):
            prev_snap = emp_snapshots[prev_emp_id]
            if prev_snap.availability_status == "AVAILABLE":
                from app.optimizer.candidates import Candidate
                from app.services.skills import skill_compatibility
                sm = (sum(skill_compatibility(prev_snap.skill_names, r) for r in tsnap.required_skills) / len(tsnap.required_skills)) if tsnap.required_skills else 0.6
                candidates.append(Candidate(employee=prev_snap, skill_match=round(sm, 4)))

        trace_list = []
        remaining_time = remaining_hours_until_deadline(tsnap.deadline, tsnap.sla_hours)
        for c in candidates:
            emp = c.employee
            util_after = (emp.current_workload_hours + tsnap.estimated_hours) / emp.max_capacity_hours if emp.max_capacity_hours else 0.0
            fairness_pen = fairness_penalty_for_candidate(util_after, mean_utilization)
            pred = predict_sla_risk_and_completion(
                task_complexity=tsnap.complexity,
                remaining_time_hours=remaining_time,
                employee_workload_ratio=emp.current_workload_hours / emp.max_capacity_hours if emp.max_capacity_hours else 0.0,
                skill_match=c.skill_match,
                task_priority=tsnap.priority,
                employee_experience_years=emp.experience_years,
                historical_completion_ratio=2.0 - emp.historical_performance_score,
            )
            pref_score = _preference_score(emp, tsnap)
            travel = _travel_minutes(emp, tsnap)

            # "Employee Agent" acceptance-likelihood signal -- a lightweight
            # multi-agent negotiation layer: rather than the optimizer only
            # asking "is this employee eligible", a second, independent
            # score asks "would this employee actually be comfortable with
            # this assignment", blending their stated preference alignment
            # with how much it would load them up relative to the team.
            # Low scores are surfaced to the manager as a pushback risk
            # instead of being silently overridden.
            acceptance_likelihood = round(0.6 * pref_score + 0.4 * (1.0 - fairness_pen), 3)

            option = AssignmentOption(
                task_id=tid, employee_id=emp.id, skill_match=c.skill_match,
                sla_risk=pred["sla_risk_probability"], preference_score=pref_score,
                travel_minutes=travel, fairness_penalty=fairness_pen,
            )
            all_options.append(option)
            trace_list.append({
                "employee_id": emp.id, "employee_name": emp.name,
                "skill_match": c.skill_match, "sla_risk": pred["sla_risk_probability"],
                "predicted_completion_hours": pred["predicted_completion_hours"],
                "workload_utilization_after": round(util_after, 3),
                "fairness_penalty": round(fairness_pen, 3),
                "preference_score": round(pref_score, 3),
                "travel_minutes": travel,
                "is_previous_assignee": emp.id == prev_emp_id,
                "skill_breakdown": c.skill_breakdown,
                "acceptance_likelihood": acceptance_likelihood,
            })
        candidate_trace[tid] = trace_list

    task_priority = {tid: s.priority for tid, s in task_snapshots.items()}
    task_hours = {tid: s.estimated_hours for tid, s in task_snapshots.items()}

    solve_result = solve(
        task_ids=list(task_snapshots.keys()),
        task_priority=task_priority,
        task_hours=task_hours,
        options=all_options,
        employee_headroom=employee_headroom,
        previous_assignment=previous_assignment,
    )

    result = AllocationRunResult()
    result.assignment = solve_result.assignment
    result.status = solve_result.status
    result.unresolved_task_ids = solve_result.unresolved_task_ids

    # ---- Verification pass: confirm hard constraints truly hold ----
    _verify_solution(solve_result.assignment, task_snapshots, emp_snapshots, employee_headroom, task_hours)

    # ---- Persist assignments + decision traces ----
    employee_by_id = {e.id: e for e in all_employees}
    for tid, chosen_emp_id in solve_result.assignment.items():
        tsnap = task_snapshots[tid]
        trace_list = candidate_trace.get(tid, [])
        chosen_trace = next((c for c in trace_list if c["employee_id"] == chosen_emp_id), None)
        rejected = [c for c in trace_list if c["employee_id"] != chosen_emp_id]

        reason_codes = _reason_codes(tid, chosen_emp_id, previous_assignment.get(tid), chosen_trace, trigger)

        task_obj = next(t for t in task_scope if t.id == tid)
        existing = db.query(Assignment).filter(Assignment.task_id == tid, Assignment.is_active == True).first()
        if existing:
            existing.is_active = False

        # Keep Employee.current_workload_hours in sync with the solver's
        # decision so subsequent optimize/reallocate calls (and the
        # workload/fairness dashboards) see true committed capacity rather
        # than the stale pre-optimization baseline.
        prev_emp_id = previous_assignment.get(tid)
        if prev_emp_id and prev_emp_id != chosen_emp_id and prev_emp_id in employee_by_id:
            employee_by_id[prev_emp_id].current_workload_hours = max(
                0.0, employee_by_id[prev_emp_id].current_workload_hours - tsnap.estimated_hours)
        if chosen_emp_id and chosen_emp_id != prev_emp_id and chosen_emp_id in employee_by_id:
            employee_by_id[chosen_emp_id].current_workload_hours += tsnap.estimated_hours

        if chosen_emp_id:
            new_assignment = Assignment(
                task_id=tid, employee_id=chosen_emp_id,
                skill_match_score=chosen_trace["skill_match"] if chosen_trace else 0.0,
                workload_score=chosen_trace["workload_utilization_after"] if chosen_trace else 0.0,
                sla_risk=chosen_trace["sla_risk"] if chosen_trace else 0.0,
                preference_score=chosen_trace["preference_score"] if chosen_trace else 0.0,
                travel_minutes=chosen_trace["travel_minutes"] if chosen_trace else 0.0,
                objective_score=solve_result.objective_value,
                is_active=True,
            )
            db.add(new_assignment)
            task_obj.status = TaskStatus.ASSIGNED
        else:
            task_obj.status = TaskStatus.UNASSIGNED

        decision_log = DecisionLog(
            task_id=tid, chosen_employee_id=chosen_emp_id,
            previous_employee_id=previous_assignment.get(tid),
            trigger=trigger,
            candidates=trace_list,
            hard_constraints_checked=["AVAILABILITY", "CAPACITY", "CERTIFICATION", "EXACTLY_ONE_ASSIGNMENT"],
            reason_codes=reason_codes,
            objective_breakdown=chosen_trace or {},
        )
        db.add(decision_log)
        result.decision_logs.append(decision_log)

    db.flush()

    # attach explanation text after logs have task/employee names resolvable
    for log in result.decision_logs:
        from app.agents.explanation import generate_explanation
        emp_name_map = {e.id: e.name for e in all_employees}
        task_title = task_snapshots[log.task_id].title
        log.explanation = generate_explanation(
            task_id=log.task_id, task_title=task_title,
            old_employee_name=emp_name_map.get(log.previous_employee_id),
            new_employee_name=emp_name_map.get(log.chosen_employee_id),
            reason_codes=log.reason_codes,
            chosen_trace=next((c for c in candidate_trace.get(log.task_id, []) if c["employee_id"] == log.chosen_employee_id), None),
        )

    db.flush()

    utils = utilization_ratios(
        [e.current_workload_hours for e in all_employees],
        [e.max_capacity_hours for e in all_employees],
    )
    result.fairness_index = jain_fairness_index(utils)
    result.duration_ms = (datetime.utcnow() - start).total_seconds() * 1000
    return result


def _verify_solution(assignment, task_snapshots, emp_snapshots, employee_headroom, task_hours):
    """Solution verifier: re-checks hard constraints on the solver's output before it is trusted."""
    used_hours: Dict[str, float] = {}
    for tid, eid in assignment.items():
        if eid is None:
            continue
        emp = emp_snapshots.get(eid)
        assert emp is not None, f"Verifier: unknown employee {eid} in solution"
        assert emp.availability_status == "AVAILABLE", f"Verifier: {eid} is not AVAILABLE but was assigned {tid}"
        used_hours[eid] = used_hours.get(eid, 0.0) + task_hours[tid]
    for eid, hours in used_hours.items():
        headroom = employee_headroom.get(eid, 0.0)
        assert hours <= headroom + 1e-6, f"Verifier: {eid} over capacity ({hours} > {headroom})"
    return True


def _reason_codes(task_id, chosen_emp_id, previous_emp_id, chosen_trace, trigger) -> List[str]:
    codes = []
    if trigger == "DISRUPTION":
        codes.append("EMPLOYEE_UNAVAILABLE")
    if chosen_emp_id is None:
        codes.append("NO_FEASIBLE_CANDIDATE")
        return codes
    if previous_emp_id and chosen_emp_id == previous_emp_id:
        codes.append("ASSIGNMENT_UNCHANGED_MINIMIZES_DISRUPTION")
    elif previous_emp_id and chosen_emp_id != previous_emp_id:
        codes.append("REASSIGNED_MINIMUM_DISRUPTION_CANDIDATE")
    if chosen_trace:
        if chosen_trace["skill_match"] >= 0.8:
            codes.append("HIGH_SKILL_MATCH")
        elif chosen_trace["skill_match"] >= 0.6:
            codes.append("ADEQUATE_SKILL_MATCH")
        if chosen_trace["workload_utilization_after"] <= 0.85:
            codes.append("SUFFICIENT_CAPACITY")
        if chosen_trace["sla_risk"] <= 0.3:
            codes.append("LOW_SLA_RISK")
        elif chosen_trace["sla_risk"] >= 0.6:
            codes.append("ELEVATED_SLA_RISK")
        if chosen_trace["preference_score"] >= 0.7:
            codes.append("MATCHES_PREFERENCE")
        if chosen_trace["fairness_penalty"] <= 0.4:
            codes.append("IMPROVES_FAIRNESS")
        breakdown = chosen_trace.get("skill_breakdown") or []
        if breakdown and all(b["matched_via"] != "exact" for b in breakdown) and any(b["matched_via"] == "transferable" for b in breakdown):
            codes.append("GRACEFUL_DEGRADATION_TRANSFERABLE_SKILL")
        acceptance = chosen_trace.get("acceptance_likelihood")
        if acceptance is not None:
            if acceptance >= 0.75:
                codes.append("HIGH_EMPLOYEE_ACCEPTANCE_LIKELIHOOD")
            elif acceptance < 0.4:
                codes.append("LOW_EMPLOYEE_ACCEPTANCE_RISK")
    return codes
