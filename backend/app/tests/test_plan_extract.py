import json
from types import SimpleNamespace

import app.plan_extract as pe


def _fake_client(raw_text):
    """Заглушка anthropic.Anthropic с фиксированным ответом."""
    usage = SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0)
    block = SimpleNamespace(type="text", text=raw_text)
    message = SimpleNamespace(content=[block], usage=usage)

    class FakeMessages:
        def create(self, **kwargs):
            return message

    return SimpleNamespace(messages=FakeMessages())


def test_extract_plan_fields_parses_valid_json(monkeypatch):
    payload = {
        "title": "Квадратные уравнения",
        "key_concepts": ["дискриминант", "теорема Виета", "корни уравнения"],
    }
    monkeypatch.setattr(pe, "_client", lambda: _fake_client(json.dumps(payload)))

    result, raw = pe.extract_plan_fields("Текст плана урока", "ru")
    assert result.title == "Квадратные уравнения"
    assert result.key_concepts == ["дискриминант", "теорема Виета", "корни уравнения"]


def test_extract_plan_fields_handles_fenced_json(monkeypatch):
    payload = {"title": "Тема", "key_concepts": ["a", "b"]}
    raw = "```json\n" + json.dumps(payload) + "\n```"
    monkeypatch.setattr(pe, "_client", lambda: _fake_client(raw))

    result, _raw = pe.extract_plan_fields("text", "kk")
    assert result.title == "Тема"
    assert result.key_concepts == ["a", "b"]
