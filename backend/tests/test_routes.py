import pytest
import io
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch
from app.main import app
from app.database import Base, get_db

TEST_DB_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_txt_note(client):
    with patch("app.routes.notes.coordinator_task") as mock_task:
        mock_task.delay.return_value = None
        file_content = b"Patient needs CBC blood test. Follow up in 2 weeks."
        response = client.post(
            "/api/notes/upload",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "note_id" in data
    assert data["status"] == "pending"


def test_upload_unsupported_type(client):
    response = client.post(
        "/api/notes/upload",
        files={"file": ("test.docx", io.BytesIO(b"content"), "application/octet-stream")},
    )
    assert response.status_code == 400


def test_get_status_not_found(client):
    response = client.get("/api/notes/nonexistent-id/status")
    assert response.status_code == 404


def test_get_status_after_upload(client):
    with patch("app.routes.notes.coordinator_task") as mock_task:
        mock_task.delay.return_value = None
        file_content = b"Patient needs CBC blood test."
        upload_resp = client.post(
            "/api/notes/upload",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        )
    note_id = upload_resp.json()["note_id"]
    status_resp = client.get(f"/api/notes/{note_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["note_id"] == note_id


def test_list_notes(client):
    with patch("app.routes.notes.coordinator_task") as mock_task:
        mock_task.delay.return_value = None
        client.post(
            "/api/notes/upload",
            files={"file": ("note1.txt", io.BytesIO(b"CBC test needed."), "text/plain")},
        )
    response = client.get("/api/notes/")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_results_not_found(client):
    response = client.get("/api/notes/nonexistent-id/results")
    assert response.status_code == 404


def test_get_results_after_upload(client):
    with patch("app.routes.notes.coordinator_task") as mock_task:
        mock_task.delay.return_value = None
        file_content = b"Patient needs CBC blood test. Follow up in 2 weeks."
        upload_resp = client.post(
            "/api/notes/upload",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        )
    note_id = upload_resp.json()["note_id"]
    results_resp = client.get(f"/api/notes/{note_id}/results")
    assert results_resp.status_code == 200
    data = results_resp.json()
    assert "tasks" in data
    assert "lab_tests" in data["tasks"]
    assert "radiology" in data["tasks"]
    assert "followups" in data["tasks"]
