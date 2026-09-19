def test_login_success(client):
    resp = client.post("/auth/login", json={"email": "manager@test.local", "password": "pass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "MANAGER"
    assert "access_token" in data


def test_login_wrong_password(client):
    resp = client.post("/auth/login", json={"email": "manager@test.local", "password": "wrong"})
    assert resp.status_code == 401


def test_unauthenticated_request_rejected(client):
    resp = client.get("/employees")
    assert resp.status_code == 401


def test_employee_role_cannot_create_employee(client, auth_headers):
    from app.database import SessionLocal
    from app.models import User, RoleEnum
    from app.auth import hash_password
    db = SessionLocal()
    db.add(User(email="emp@test.local", hashed_password=hash_password("pass123"),
                full_name="Line Employee", role=RoleEnum.EMPLOYEE))
    db.commit()
    db.close()

    resp = client.post("/auth/login", json={"email": "emp@test.local", "password": "pass123"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post("/employees", json={
        "name": "New Person", "email": "new@test.local", "role": "Engineer",
    }, headers=headers)
    assert create_resp.status_code == 403


def test_manager_can_create_employee(client, auth_headers):
    resp = client.post("/employees", json={
        "name": "New Person", "email": "new@test.local", "role": "Engineer",
        "skills": [{"skill_name": "Python", "proficiency": 0.8}],
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Person"
