def test_create_employee(client, auth_headers):
    resp = client.post("/employees", json={
        "name": "Alice", "email": "alice@test.local", "role": "Backend Engineer",
        "experience_years": 3.5, "max_capacity_hours": 40,
        "skills": [{"skill_name": "Python", "proficiency": 0.9}, {"skill_name": "FastAPI", "proficiency": 0.8}],
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Alice"
    assert len(data["skills"]) == 2
    assert data["availability_status"] == "AVAILABLE"


def test_list_employees(client, auth_headers):
    client.post("/employees", json={"name": "Bob", "email": "bob@test.local", "role": "QA"}, headers=auth_headers)
    resp = client.get("/employees", headers=auth_headers)
    assert resp.status_code == 200
    assert any(e["name"] == "Bob" for e in resp.json())


def test_create_task(client, auth_headers):
    resp = client.post("/tasks", json={
        "title": "Build reporting dashboard", "description": "Quarterly reporting dashboard",
        "priority": "HIGH", "estimated_hours": 10, "required_skills": [{"skill_name": "React", "min_proficiency": 0.5}],
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Build reporting dashboard"
    assert data["status"] == "UNASSIGNED"
    assert "React" in data["required_skills"]


def test_list_tasks_filter_by_priority(client, auth_headers):
    client.post("/tasks", json={"title": "Urgent fix", "priority": "CRITICAL", "estimated_hours": 4}, headers=auth_headers)
    client.post("/tasks", json={"title": "Low priority cleanup", "priority": "LOW", "estimated_hours": 2}, headers=auth_headers)
    resp = client.get("/tasks", params={"priority": "CRITICAL"}, headers=auth_headers)
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()]
    assert "Urgent fix" in titles
    assert "Low priority cleanup" not in titles


def test_employee_availability_update(client, auth_headers):
    emp_resp = client.post("/employees", json={"name": "Carla", "email": "carla@test.local", "role": "Engineer"}, headers=auth_headers)
    emp_id = emp_resp.json()["id"]
    resp = client.patch(f"/employees/{emp_id}/availability", json={
        "status": "UNAVAILABLE", "reason": "vacation", "trigger_reallocation": True,
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["new_status"] == "UNAVAILABLE"

    emp_check = client.get(f"/employees/{emp_id}", headers=auth_headers)
    assert emp_check.json()["availability_status"] == "UNAVAILABLE"
