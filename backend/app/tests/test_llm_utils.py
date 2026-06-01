import pytest

from app.llm_utils import extract_json


def test_extract_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_fenced_json():
    raw = 'Вот ответ:\n```json\n{"a": 2}\n```\nКонец.'
    assert extract_json(raw) == {"a": 2}


def test_extract_balanced_object_from_noise():
    raw = 'prefix {"a": {"b": 3}} suffix'
    assert extract_json(raw) == {"a": {"b": 3}}


def test_extract_raises_on_garbage():
    with pytest.raises(ValueError):
        extract_json("нет тут json")
