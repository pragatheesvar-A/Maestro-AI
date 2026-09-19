from app.optimizer.solver import solve, AssignmentOption


def _opt(task_id, employee_id, skill=0.8, sla=0.2, pref=0.5, travel=0.0, fairness=0.3):
    return AssignmentOption(task_id=task_id, employee_id=employee_id, skill_match=skill,
                             sla_risk=sla, preference_score=pref, travel_minutes=travel, fairness_penalty=fairness)


def test_solver_assigns_every_task_when_feasible():
    options = [_opt("T1", "E1"), _opt("T1", "E2"), _opt("T2", "E1"), _opt("T2", "E2")]
    result = solve(
        task_ids=["T1", "T2"], task_priority={"T1": "HIGH", "T2": "MEDIUM"},
        task_hours={"T1": 5, "T2": 5}, options=options,
        employee_headroom={"E1": 20, "E2": 20},
    )
    assert result.assignment["T1"] is not None
    assert result.assignment["T2"] is not None
    assert result.unresolved_task_ids == []


def test_solver_respects_capacity_hard_constraint():
    # Only one employee, with just enough headroom for ONE of the two tasks.
    options = [_opt("T1", "E1"), _opt("T2", "E1")]
    result = solve(
        task_ids=["T1", "T2"], task_priority={"T1": "HIGH", "T2": "HIGH"},
        task_hours={"T1": 10, "T2": 10}, options=options,
        employee_headroom={"E1": 10},  # only room for one 10h task
    )
    assigned = [t for t, e in result.assignment.items() if e is not None]
    assert len(assigned) == 1  # never both -- would violate capacity
    assert len(result.unresolved_task_ids) == 1


def test_solver_never_assigns_employee_with_no_option():
    # E2 has no AssignmentOption for T1 at all (simulating hard-filtered
    # unavailability/certification failure upstream) -- solver must not
    # invent an assignment to E2.
    options = [_opt("T1", "E1")]
    result = solve(
        task_ids=["T1"], task_priority={"T1": "MEDIUM"}, task_hours={"T1": 5},
        options=options, employee_headroom={"E1": 20, "E2": 20},
    )
    assert result.assignment["T1"] == "E1"


def test_solver_prefers_higher_skill_match_when_tied_otherwise():
    options = [
        _opt("T1", "E1", skill=0.95, sla=0.1, fairness=0.1),
        _opt("T1", "E2", skill=0.4, sla=0.1, fairness=0.1),
    ]
    result = solve(
        task_ids=["T1"], task_priority={"T1": "MEDIUM"}, task_hours={"T1": 5},
        options=options, employee_headroom={"E1": 20, "E2": 20},
    )
    assert result.assignment["T1"] == "E1"


def test_solver_leaves_task_unassigned_when_no_candidates():
    result = solve(
        task_ids=["T1"], task_priority={"T1": "MEDIUM"}, task_hours={"T1": 5},
        options=[], employee_headroom={},
    )
    assert result.assignment["T1"] is None
    assert "T1" in result.unresolved_task_ids
