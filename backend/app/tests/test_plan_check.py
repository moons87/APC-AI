import json
from types import SimpleNamespace

import app.plan_check as pc


def _fake_client(raw_text):
    """Возвращает объект-заглушку anthropic.Anthropic с фиксированным ответом."""
    usage = SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0)
    block = SimpleNamespace(type="text", text=raw_text)
    message = SimpleNamespace(content=[block], usage=usage)

    class FakeMessages:
        def create(self, **kwargs):
            return message

    return SimpleNamespace(messages=FakeMessages())


def test_normalize_verdict_maps_tokens():
    assert pc.normalize_verdict("ҚАЙТА_ӨҢДЕУГЕ") == "rework"
    assert pc.normalize_verdict("ІШІНАРА_ҚАБЫЛДАНСЫН") == "partial"
    assert pc.normalize_verdict("ТОЛЫҚ_БЕКІТІЛСІН") == "approved"
    assert pc.normalize_verdict(None) is None


def test_check_plan_parses_valid_json(monkeypatch):
    payload = {
        "verdict": "ІШІНАРА_ҚАБЫЛДАНСЫН",
        "summary": "Бар кемшіліктер бар.",
        "errors": [
            {
                "category": "bloom",
                "type": "Блум қатесі",
                "description": "Пассив етістік",
                "example": "...баптау",
                "suggestions": ["баптайды", "реттейді"],
            }
        ],
        "optimized_plan": "Түзетілген нұсқа",
    }
    monkeypatch.setattr(pc, "_client", lambda: _fake_client(json.dumps(payload)))

    result, raw, is_raw = pc.check_plan("РУП сварка", "kk", "Жоспар мәтіні")
    assert is_raw is False
    assert result.verdict == "partial"
    assert result.summary == "Бар кемшіліктер бар."
    assert len(result.errors) == 1
    assert result.errors[0].type == "Блум қатесі"
    assert result.errors[0].category == "bloom"
    assert result.errors[0].suggestions == ["баптайды", "реттейді"]
    assert result.optimized_plan == "Түзетілген нұсқа"


def test_check_plan_handles_fenced_json(monkeypatch):
    payload = {"verdict": "ТОЛЫҚ_БЕКІТІЛСІН", "summary": "Ок", "errors": [], "optimized_plan": "X"}
    raw = "```json\n" + json.dumps(payload) + "\n```"
    monkeypatch.setattr(pc, "_client", lambda: _fake_client(raw))

    result, _raw, is_raw = pc.check_plan("t", "ru", "text")
    assert is_raw is False
    assert result.verdict == "approved"


def test_check_plan_raw_fallback_on_garbage(monkeypatch):
    monkeypatch.setattr(pc, "_client", lambda: _fake_client("Извините, не смог."))

    result, raw, is_raw = pc.check_plan("t", "ru", "text")
    assert is_raw is True
    assert result.verdict is None
    assert result.errors == []
    assert result.optimized_plan == "Извините, не смог."
    assert raw == "Извините, не смог."
