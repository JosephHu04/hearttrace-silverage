import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret-not-for-production-32-bytes-minimum"
os.environ["SEED_DEMO_DATA"] = "true"

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine
from app.main import app


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/demo-login", json={"actorId": "staff-admin-001"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


@pytest.fixture
def family_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/demo-login", json={"actorId": "family-demo-001"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


@pytest.fixture
def no_access_family_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/demo-login", json={"actorId": "family-no-access-001"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}
