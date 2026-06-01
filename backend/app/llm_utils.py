"""Общие утилиты для разбора ответов LLM."""
from __future__ import annotations

import json
import re


def extract_json(text: str) -> dict:
    """Достаёт первый сбалансированный JSON-объект из ответа модели.

    Устойчив к markdown-обёрткам ```json ... ``` и тексту до/после объекта.
    Бросает ValueError, если валидный объект не найден.
    """
    # Сначала пробуем как есть.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Убираем markdown-ограждения ```json ... ```
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    # Ищем первый сбалансированный объект по фигурным скобкам.
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    return json.loads(candidate)
    raise ValueError("В ответе модели не найден валидный JSON")
