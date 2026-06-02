import io

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
from app.database import Base, get_db
from app.schemas import LLMPlanExtract


def _make_client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_get_db

    def fake_extract(plan_text, language):
        return LLMPlanExtract(title="Тема", key_concepts=["a", "b"]), "{}"

    monkeypatch.setattr(main, "extract_plan_fields", fake_extract)
    return TestClient(main.app)


def test_plan_extract_with_text(monkeypatch):
    client = _make_client(monkeypatch)
    resp = client.post(
        "/lessons/plan-extract",
        data={"language": "ru", "text": "План урока"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "Тема"
    assert body["key_concepts"] == ["a", "b"]
    main.app.dependency_overrides.clear()


def test_plan_extract_with_file(monkeypatch):
    client = _make_client(monkeypatch)
    resp = client.post(
        "/lessons/plan-extract",
        data={"language": "ru"},
        files={"file": ("plan.txt", io.BytesIO("План".encode("utf-8")), "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["key_concepts"] == ["a", "b"]
    main.app.dependency_overrides.clear()


def test_plan_extract_requires_input(monkeypatch):
    client = _make_client(monkeypatch)
    resp = client.post("/lessons/plan-extract", data={"language": "ru"})
    assert resp.status_code == 400
    main.app.dependency_overrides.clear()


def test_plan_extract_rejects_bad_ext(monkeypatch):
    client = _make_client(monkeypatch)
    resp = client.post(
        "/lessons/plan-extract",
        data={"language": "ru"},
        files={"file": ("plan.exe", io.BytesIO(b"x"), "application/octet-stream")},
    )
    assert resp.status_code == 400
    main.app.dependency_overrides.clear()


def test_plan_extract_rejects_oversize_file(monkeypatch):
    client = _make_client(monkeypatch)
    monkeypatch.setattr(main, "MAX_PLAN_UPLOAD_MB", 0)
    resp = client.post(
        "/lessons/plan-extract",
        data={"language": "ru"},
        files={"file": ("big.txt", io.BytesIO(b"x" * 10), "text/plain")},
    )
    assert resp.status_code == 413
    main.app.dependency_overrides.clear()
