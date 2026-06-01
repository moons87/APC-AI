import io

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
from app.database import Base, get_db
from app.schemas import LLMPlanCheck, PlanError


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

    def fake_check_plan(title, language, plan_text):
        result = LLMPlanCheck(
            verdict="partial",
            summary="Кратко",
            errors=[PlanError(type="Дублікат", description="d", example="e")],
            optimized_plan="Исправленный план",
        )
        return result, '{"verdict":"partial"}', False

    monkeypatch.setattr(main, "check_plan", fake_check_plan)
    return TestClient(main.app)


def test_check_plan_with_text(monkeypatch):
    client = _make_client(monkeypatch)
    resp = client.post(
        "/plans/check",
        data={"title": "РУП", "language": "ru", "text": "Текст плана"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verdict"] == "partial"
    assert body["status"] == "done"
    assert body["errors"][0]["type"] == "Дублікат"
    assert body["optimized_plan"] == "Исправленный план"

    lst = client.get("/plans").json()
    assert len(lst) == 1
    assert lst[0]["title"] == "РУП"
    main.app.dependency_overrides.clear()


def test_check_plan_with_file(monkeypatch):
    client = _make_client(monkeypatch)
    resp = client.post(
        "/plans/check",
        data={"title": "Из файла", "language": "kk"},
        files={"file": ("plan.txt", io.BytesIO("Жоспар".encode("utf-8")), "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    pid = resp.json()["id"]

    detail = client.get(f"/plans/{pid}").json()
    assert detail["source_filename"] == "plan.txt"
    assert detail["verdict"] == "partial"
    main.app.dependency_overrides.clear()


def test_check_plan_requires_input(monkeypatch):
    client = _make_client(monkeypatch)
    resp = client.post("/plans/check", data={"title": "Пусто", "language": "ru"})
    assert resp.status_code == 400
    main.app.dependency_overrides.clear()
