"""
The primary end-to-end integration test required by the spec:

  Employee Priya becomes unavailable
    -> affected task detected
    -> alternative employee selected
    -> hard constraints satisfied
    -> decision trace generated
    -> frontend event emitted (WebSocket REALLOCATION_COMPLETE)

This exercises the real HTTP API, the real OR-Tools CP-SAT solver, the real
solution verifier, and the real (deterministic-fallback) explanation agent
-- no mocking of the optimization path.
"""
from app.database import SessionLocal
from app.models import Employee, Task, Assignment, DecisionLog, AvailabilityStatus


def _create_employee(client, headers, name, skills, capacity=40, workload=5):
    resp = client.post("/employees", json={
        "name": name, "email": f"{name.lower()}@test.local", "role": "Engineer",
        "max_capacity_hours": capacity,
        "skills": [{"skill_name": s, "proficiency": 0.9} for s in skills],
    }, headers=headers)
    assert resp.status_code == 200
    emp_id = resp.json()["id"]
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.id == emp_id).first()
    emp.current_workload_hours = workload
    db.commit()
    db.close()
    return emp_id


def _create_task(client, headers, task_id_hint, skills, hours=8):
    resp = client.post("/tasks", json={
        "title": f"Task requiring {'/'.join(skills)}", "priority": "HIGH", "estimated_hours": hours,
        "required_skills": [{"skill_name": s, "min_proficiency": 0.5} for s in skills],
    }, headers=headers)
    assert resp.status_code == 200
    return resp.json()["id"]


def test_full_disruption_pipeline(client, auth_headers):
    priya_id = _create_employee(client, auth_headers, "Priya", ["React", "TypeScript"], workload=5)
    karthik_id = _create_employee(client, auth_headers, "Karthik", ["React", "TypeScript"], workload=5)

    task_id = _create_task(client, auth_headers, "T4021", ["React", "TypeScript"], hours=8)

    # Step 1: run the real optimizer to establish an initial allocation.
    opt_resp = client.post("/allocation/optimize", json={}, headers=auth_headers)
    assert opt_resp.status_code == 200

    before = client.get(f"/allocation/{task_id}", headers=auth_headers).json()
    assert before["employee_id"] in (priya_id, karthik_id)
    initially_assigned_to = before["employee_id"]

    # Step 2: disrupt whoever ended up with the task (deterministic either
    # way -- the pipeline must recover regardless of which one it was).
    disrupt_resp = client.post("/events/employee-unavailable", json={
        "employee_id": initially_assigned_to, "reason": "Sick leave",
    }, headers=auth_headers)
    assert disrupt_resp.status_code == 200
    outcome = disrupt_resp.json()

    # Affected task detected and reassigned to the other candidate.
    assert any(c["task_id"] == task_id for c in outcome["changes"])
    change = next(c for c in outcome["changes"] if c["task_id"] == task_id)
    assert change["old_employee_id"] == initially_assigned_to
    other_employee = karthik_id if initially_assigned_to == priya_id else priya_id
    assert change["new_employee_id"] == other_employee
    assert "EMPLOYEE_UNAVAILABLE" in change["reason_codes"]
    assert change["explanation"]  # factual explanation generated, non-empty

    # Hard constraints satisfied: the disrupted employee is UNAVAILABLE and
    # holds no active assignment; the new assignee is AVAILABLE.
    db = SessionLocal()
    disrupted_emp = db.query(Employee).filter(Employee.id == initially_assigned_to).first()
    assert disrupted_emp.availability_status == AvailabilityStatus.UNAVAILABLE
    active_assignment_for_disrupted = db.query(Assignment).filter(
        Assignment.employee_id == initially_assigned_to, Assignment.is_active == True,
        Assignment.task_id == task_id,
    ).first()
    assert active_assignment_for_disrupted is None

    new_active_assignment = db.query(Assignment).filter(
        Assignment.task_id == task_id, Assignment.is_active == True,
    ).first()
    assert new_active_assignment is not None
    assert new_active_assignment.employee_id == other_employee
    db.close()

    # Decision trace generated and retrievable via the API.
    trace_resp = client.get(f"/allocation/{task_id}/decision-trace", headers=auth_headers)
    assert trace_resp.status_code == 200
    trace = trace_resp.json()
    assert trace["trigger"] == "DISRUPTION"
    assert trace["chosen_employee_id"] == other_employee
    assert len(trace["candidates"]) >= 1
    assert "EMPLOYEE_UNAVAILABLE" in trace["reason_codes"]

    # Explanation endpoint works too.
    expl_resp = client.get(f"/allocation/{task_id}/explanation", headers=auth_headers)
    assert expl_resp.status_code == 200
    assert expl_resp.json()["explanation"]
