import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force an isolated on-disk SQLite test database BEFORE any app module (which
# reads settings at import time) is imported.
os.environ["DATABASE_URL"] = "sqlite:///./test_smartalloc.db"
os.environ["ANTHROPIC_API_KEY"] = ""  # force deterministic offline fallbacks in tests

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import User, RoleEnum
from app.auth import hash_password


@pytest.fixture(scope="function", autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(User(email="admin@test.local", hashed_password=hash_password("pass123"),
                full_name="Test Admin", role=RoleEnum.ADMIN))
    db.add(User(email="manager@test.local", hashed_password=hash_password("pass123"),
                full_name="Test Manager", role=RoleEnum.MANAGER))
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def manager_token(client):
    resp = client.post("/auth/login", json={"email": "manager@test.local", "password": "pass123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(manager_token):
    return {"Authorization": f"Bearer {manager_token}"}
