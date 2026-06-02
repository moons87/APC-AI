"""Извлечение полей урока (тема + ключевые понятия) из плана через Claude.

Синхронный одношаговый вызов: системный промпт помечен cache_control, ответ
ожидается строго в JSON и валидируется Pydantic-схемой LLMPlanExtract. Результат
используется фронтендом для предзаполнения формы загрузки урока — пользователь
проверяет и правит значения перед запуском анализа.
"""
from __future__ import annotations

import logging
import os

import anthropic

from .llm_utils import extract_json
from .schemas import LLMPlanExtract

logger = logging.getLogger(__name__)

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_PLAN_CHARS = int(os.getenv("MAX_PLAN_CHARS", "180000"))
# Ответ короткий (тема + список понятий), поэтому потолок небольшой.
MAX_OUTPUT_TOKENS = int(os.getenv("PLAN_EXTRACT_MAX_OUTPUT_TOKENS", "1500"))

SYSTEM_PROMPT = """Ты — методист, который разбирает план урока (КСП/ОӘЖ/конспект \
или свободный текст) и извлекает из него два поля для последующего анализа записи урока.

Верни результат СТРОГО в виде одного JSON-объекта без какого-либо текста до или после \
него, без markdown-обёрток. Структура ответа:

{
  "title": "короткая формулировка темы урока",
  "key_concepts": ["понятие 1", "понятие 2"]
}

Правила:
- title — тема урока одной строкой. Если тема явно не указана — сформулируй её кратко \
по содержанию плана.
- key_concepts — ключевые понятия и термины, которые по плану должны прозвучать на уроке. \
Бери формулировки из плана, без воды и без целей/этапов — только понятия. Если понятий \
нет — верни пустой список [].
- Весь текст (title, key_concepts) — на языке, указанном в запросе."""


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY не задан в окружении")
    return anthropic.Anthropic(api_key=api_key)


def _lang_instruction(language: str) -> str:
    return "Қазақ тілінде жауап бер." if language == "kk" else "Отвечай на русском языке."


def extract_plan_fields(plan_text: str, language: str) -> tuple[LLMPlanExtract, str]:
    """Вызывает Claude и возвращает (распарсенные поля, сырой ответ)."""
    text = plan_text
    if len(text) > MAX_PLAN_CHARS:
        text = text[:MAX_PLAN_CHARS] + "\n…[текст обрезан по длине]…"

    user_message = (
        f"{_lang_instruction(language)}\n\n"
        f"ТЕКСТ ПЛАНА УРОКА:\n{text}\n\n"
        f"Верни ответ строго в формате JSON, описанном в инструкции."
    )

    response = _client().messages.create(
        model=MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = "".join(b.text for b in response.content if b.type == "text")
    logger.info(
        "PlanExtract usage: in=%s out=%s cache_read=%s",
        response.usage.input_tokens,
        response.usage.output_tokens,
        getattr(response.usage, "cache_read_input_tokens", None),
    )

    data = extract_json(raw_text)
    result = LLMPlanExtract.model_validate(data)
    return result, raw_text
