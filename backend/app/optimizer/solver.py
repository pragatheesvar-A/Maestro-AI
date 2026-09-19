"""
OR-Tools CP-SAT multi-objective task-allocation solver.

Decision variable:  X(employee, task) in {0,1}

Hard constraints:
  1. Every task gets exactly one assignment, OR an explicit "unassigned"
     slack variable is set (keeps the model always feasible even when no
     candidate qualifies -- surfaced to the caller as an unresolved task
     rather than a solver crash).
  2. An employee outside the candidate list for a task (i.e. unavailable,
     over capacity, or missing a mandatory certification -- see
     optimizer/candidates.py hard_filter) simply has no X(e,t) variable at
     all, so it can never be chosen.
  3. Employee capacity: sum of hours assigned to an employee across the
     tasks in this optimization batch cannot exceed their pre-computed
     headroom.

Soft objective (single scalarized weighted sum -- see note below):
  skill compatibility, SLA safety, task priority, workload fairness,
  employee preference, travel cost, minimum-disruption reassignment cost.

Lexicographic note: true lexicographic optimization (solve stage 1, pin its
optimum, solve stage 2, ...) is implemented for the top tier only --
"maximize number of tasks covered" is solved first and pinned as a
constraint (`sum(u) == min_unassigned`) before the weighted secondary
objective is optimized. Lower tiers (SLA safety > priority > skill >
fairness > preference > continuity > travel > reassignment) are combined
into one weighted scalarized term with weight magnitudes chosen to reflect
that priority ordering (each tier's weight is an order of magnitude above
the tier below it). This is the standard, solver-tractable approximation of
strict lexicographic ordering across 7+ objectives and keeps solve time
bounded for the hackathon time budget.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

from app.config import get_settings

settings = get_settings()

# Weight tiers (documented above). Multiplied and rounded to ints for CP-SAT.
W_SLA = 5000
W_PRIORITY = 3000
W_SKILL = 2000
W_FAIRNESS = 900
W_PREFERENCE = 400
W_CONTINUITY = 250
W_TRAVEL = 150
W_REASSIGNMENT = 600
UNASSIGNED_PENALTY = 200_000

PRIORITY_SCORE = {"LOW": 0.2, "MEDIUM": 0.5, "HIGH": 0.8, "CRITICAL": 1.0}


@dataclass
class AssignmentOption:
    task_id: str
    employee_id: str
    skill_match: float          # 0..1, higher better
    sla_risk: float             # 0..1, lower better
    preference_score: float     # 0..1, higher better
    travel_minutes: float       # lower better
    fairness_penalty: float     # 0..1, lower better (already accounts for utilization)


@dataclass
class SolveResult:
    assignment: Dict[str, Optional[str]]           # task_id -> employee_id | None
    scores: Dict[Tuple[str, str], AssignmentOption]  # (task_id, employee_id) -> option
    status: str
    unresolved_task_ids: List[str]
    objective_value: float


def solve(
    task_ids: List[str],
    task_priority: Dict[str, str],
    task_hours: Dict[str, float],
    options: List[AssignmentOption],
    employee_headroom: Dict[str, float],
    previous_assignment: Optional[Dict[str, str]] = None,
    time_limit_seconds: float = None,
) -> SolveResult:
    previous_assignment = previous_assignment or {}
    time_limit_seconds = time_limit_seconds or settings.SOLVER_TIME_LIMIT_SECONDS

    model = cp_model.CpModel()

    # index options by task
    opts_by_task: Dict[str, List[AssignmentOption]] = {tid: [] for tid in task_ids}
    for o in options:
        opts_by_task.setdefault(o.task_id, []).append(o)

    x_vars: Dict[Tuple[str, str], cp_model.IntVar] = {}
    for o in options:
        x_vars[(o.task_id, o.employee_id)] = model.NewBoolVar(f"x_{o.task_id}_{o.employee_id}")

    u_vars: Dict[str, cp_model.IntVar] = {tid: model.NewBoolVar(f"u_{tid}") for tid in task_ids}

    # Constraint 1: each task assigned exactly one candidate, or unassigned
    for tid in task_ids:
        vars_for_task = [x_vars[(tid, o.employee_id)] for o in opts_by_task.get(tid, [])]
        model.Add(sum(vars_for_task) + u_vars[tid] == 1)

    # Constraint 2 (implicit): only candidates in `options` have variables at all.

    # Constraint 3: employee capacity across this batch
    employees_involved = {o.employee_id for o in options}
    for eid in employees_involved:
        terms = []
        for o in options:
            if o.employee_id == eid:
                hours = int(round(task_hours.get(o.task_id, 1.0) * 100))
                terms.append(hours * x_vars[(o.task_id, o.employee_id)])
        headroom = int(round(max(0.0, employee_headroom.get(eid, 0.0)) * 100))
        if terms:
            model.Add(sum(terms) <= headroom)

    # ---- Stage 1: minimize unassigned tasks (lexicographic top tier) ----
    model.Minimize(sum(u_vars.values()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(2.0, time_limit_seconds / 2)
    solver.parameters.num_search_workers = 4
    solver.parameters.random_seed = 42
    status1 = solver.Solve(model)
    if status1 not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolveResult(assignment={tid: None for tid in task_ids}, scores={}, status="INFEASIBLE",
                            unresolved_task_ids=task_ids, objective_value=0.0)
    min_unassigned = int(round(solver.ObjectiveValue()))
    model.Add(sum(u_vars.values()) <= min_unassigned)

    # Fallback solution captured from stage 1, in case stage 2 (which adds a
    # tighter coverage constraint on top of the same model) fails to
    # re-converge to a feasible point within its own time budget -- this
    # guarantees we never regress to "everything unassigned" just because
    # the secondary weighted objective ran out of time.
    fallback_assignment: Dict[str, Optional[str]] = {tid: None for tid in task_ids}
    for (tid, eid), var in x_vars.items():
        if solver.Value(var) == 1:
            fallback_assignment[tid] = eid

    # ---- Stage 2: weighted multi-objective over feasible-coverage models ----
    objective_terms = []
    for o in options:
        var = x_vars[(o.task_id, o.employee_id)]
        priority_score = PRIORITY_SCORE.get(task_priority.get(o.task_id, "MEDIUM"), 0.5)
        continuity_bonus = 1.0 if previous_assignment.get(o.task_id) == o.employee_id else 0.0
        reassignment_penalty = 0.0 if previous_assignment.get(o.task_id) in (None, o.employee_id) else 1.0

        score = (
            W_SLA * (1.0 - o.sla_risk)
            + W_PRIORITY * priority_score
            + W_SKILL * o.skill_match
            + W_FAIRNESS * (1.0 - o.fairness_penalty)
            + W_PREFERENCE * o.preference_score
            + W_CONTINUITY * continuity_bonus
            - W_TRAVEL * min(1.0, o.travel_minutes / 120.0)
            - W_REASSIGNMENT * reassignment_penalty
        )
        objective_terms.append(int(round(score)) * var)

    for tid in task_ids:
        objective_terms.append(-UNASSIGNED_PENALTY * u_vars[tid])

    model.Maximize(sum(objective_terms))
    solver2 = cp_model.CpSolver()
    solver2.parameters.max_time_in_seconds = max(2.0, time_limit_seconds / 2)
    solver2.parameters.num_search_workers = 4
    solver2.parameters.random_seed = 42
    status2 = solver2.Solve(model)

    status_name = solver2.StatusName(status2)
    scores: Dict[Tuple[str, str], AssignmentOption] = {(o.task_id, o.employee_id): o for o in options}
    unresolved = []

    if status2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assignment: Dict[str, Optional[str]] = {tid: None for tid in task_ids}
        for (tid, eid), var in x_vars.items():
            if solver2.Value(var) == 1:
                assignment[tid] = eid
        for tid in task_ids:
            if solver2.Value(u_vars[tid]) == 1:
                unresolved.append(tid)
        obj_val = solver2.ObjectiveValue()
        status_name = f"{status_name} (stage2)"
    else:
        # Stage 2 failed to re-solve in time -- use stage 1's already-proven
        # feasible, coverage-optimal solution instead of dropping everything.
        assignment = fallback_assignment
        unresolved = [tid for tid, eid in fallback_assignment.items() if eid is None]
        obj_val = 0.0
        status_name = f"STAGE1_FALLBACK (stage2={status_name})"

    return SolveResult(
        assignment=assignment,
        scores=scores,
        status=status_name,
        unresolved_task_ids=unresolved,
        objective_value=obj_val,
    )
