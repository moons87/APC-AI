"""LLM-анализ транскрипта через Anthropic API.

Решения:
- Системный промпт (объёмная инструкция + JSON-схема) помечен cache_control,
  чтобы при повторных запросах он читался из prompt-кэша Anthropic — это дешевле
  и быстрее, т.к. инструкция не меняется между уроками.
- Модель просим вернуть СТРОГО JSON. На случай, если она обернёт ответ в ```json
  или добавит текст, парсер вытаскивает первый сбалансированный JSON-объект.
- Распарсенный JSON валидируется Pydantic-схемой LLMAnalysis перед сохранением.
"""
from __future__ import annotations

import logging
import os
from typing import List

import anthropic

from .llm_utils import extract_json
from .schemas import LLMAnalysis

logger = logging.getLogger(__name__)

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
# Транскрипт урока (даже на час) легко влезает в окно Sonnet (200k токенов),
# поэтому чанкинг текста для LLM не требуется. Ограничение — лишь страховка.
MAX_TRANSCRIPT_CHARS = int(os.getenv("MAX_TRANSCRIPT_CHARS", "180000"))

SYSTEM_PROMPT = """Ты — опытный методист, который анализирует качество проведения урока \
по его транскрипту с разметкой говорящих и таймкодами.

В транскрипте реплики помечены НЕЙТРАЛЬНЫМИ ярлыками говорящих: [СПИКЕР 1], [СПИКЕР 2] и т.д. \
Это анонимные кластеры диаризации — кто из них преподаватель, а кто студенты, заранее НЕ известно. \
Таймкоды в формате [MM:SS] показывают начало реплики.

Твоя первая задача — определить роль КАЖДОГО спикера ПО СМЫСЛУ его речи, а не по объёму. \
Признаки преподавателя: ведёт урок, ставит цель, объясняет материал, даёт инструкции и задания, \
обращается ко всему классу, задаёт вопросы классу, оценивает ответы. Признаки студента: отвечает \
на вопросы, чаще короткими репликами, спрашивает разрешения/уточняет. Обычно преподаватель один. \
Если диаризация разбила одного человека на несколько ярлыков — пометь их все одинаково.

Проанализируй урок и верни результат СТРОГО в виде одного JSON-объекта без какого-либо \
текста до или после него, без markdown-обёрток. Структура ответа:

{
  "speaker_roles": {            // роль КАЖДОГО ярлыка из транскрипта; значения строго "teacher" или "student"
    "СПИКЕР 1": "teacher",
    "СПИКЕР 2": "student"
  },
  "total_questions": int,        // сколько всего вопросов задано (преимущественно преподавателем)
  "open_questions": int,         // открытые/проблемные вопросы (требуют развёрнутого ответа)
  "closed_questions": int,       // закрытые вопросы (да/нет, один факт)
  "covered_concepts": [string],  // ключевые понятия из заданного списка, которые БЫЛИ упомянуты
  "missing_concepts": [string],  // ключевые понятия из списка, которые НЕ упоминались
  "structure_present": {
    "intro": bool,        // есть ли вступление/постановка цели
    "explanation": bool,  // есть ли объяснение нового материала
    "practice": bool,     // есть ли закрепление/практика
    "summary": bool       // есть ли подведение итогов
  },
  "recommendations": [string]    // 3-6 конкретных рекомендаций преподавателю, на русском языке
}

Правила:
- speaker_roles ОБЯЗАН содержать каждый ярлык [СПИКЕР N], встречающийся в транскрипте, со значением \
строго "teacher" или "student". Долю времени речи НЕ считай — баланс вычисляется отдельно по длительностям.
- В covered_concepts и missing_concepts используй ТОЛЬКО формулировки из переданного списка \
ключевых понятий; их объединение должно покрывать весь список.
- open_questions + closed_questions не должны превышать total_questions.
- Рекомендации — практичные и привязанные к данным урока (баланс речи, типы вопросов, \
пропущенные понятия, недостающие части структуры)."""


def _build_user_message(title: str, key_concepts: List[str], transcript: str, speaker_stats: dict) -> str:
    concepts_text = "\n".join(f"- {c}" for c in key_concepts) if key_concepts else "(не заданы)"
    stats_text = (
        "\n".join(f"- {role}: {sec:.0f} сек" for role, sec in speaker_stats.items())
        if speaker_stats
        else "(нет данных диаризации)"
    )
    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        transcript = transcript[:MAX_TRANSCRIPT_CHARS] + "\n…[транскрипт обрезан по длине]…"

    return f"""ТЕМА УРОКА: {title}

КЛЮЧЕВЫЕ ПОНЯТИЯ ПЛАНА УРОКА:
{concepts_text}

ДЛИТЕЛЬНОСТЬ РЕЧИ ПО СПИКЕРАМ (по данным диаризации, секунды):
{stats_text}

ТРАНСКРИПТ УРОКА:
{transcript}

Верни анализ строго в формате JSON, описанном в инструкции."""


def _compute_balance(speaker_roles: dict, speaker_stats: dict) -> tuple[float, float]:
    """Доли речи преподавателя/студентов из РЕАЛЬНЫХ длительностей диаризации.

    Идём по фактическим длительностям (speaker_stats), а роль берём из ответа LLM.
    Ярлык, который модель не классифицировала, считаем студентом — чтобы ни одна
    секунда речи не потерялась в балансе.
    """
    teacher_sec = 0.0
    student_sec = 0.0
    for label, sec in speaker_stats.items():
        role = (speaker_roles.get(label) or "student").strip().lower()
        if role == "teacher":
            teacher_sec += sec
        else:
            student_sec += sec
    total = teacher_sec + student_sec
    if total <= 0:
        return 0.0, 0.0
    return round(teacher_sec / total, 4), round(student_sec / total, 4)


def _build_display_labels(speaker_roles: dict, speaker_stats: dict) -> dict:
    """Карта нейтральный ярлык -> человекочитаемая роль для переразметки транскрипта.

    Преподаватель(и) -> ПРЕПОДАВАТЕЛЬ; студенты -> СТУДЕНТ 1..k по убыванию времени.
    """
    students = []
    display: dict = {}
    for label in speaker_stats:
        role = (speaker_roles.get(label) or "student").strip().lower()
        if role == "teacher":
            display[label] = "ПРЕПОДАВАТЕЛЬ"
        else:
            students.append(label)
    students.sort(key=lambda l: speaker_stats.get(l, 0.0), reverse=True)
    for i, label in enumerate(students, start=1):
        display[label] = f"СТУДЕНТ {i}"
    return display


def analyze_transcript(
    title: str,
    key_concepts: List[str],
    transcript: str,
    speaker_stats: dict,
) -> tuple[LLMAnalysis, str, dict]:
    """Вызывает Claude и возвращает (результат, сырой ответ, карту переразметки).

    Роли спикеров определяет модель по смыслу речи (speaker_roles), а баланс речи
    мы считаем здесь из реальных длительностей диаризации. Третий элемент —
    карта {«СПИКЕР N»: «ПРЕПОДАВАТЕЛЬ»|«СТУДЕНТ k»} для relabel_transcript().
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY не задан в окружении")

    client = anthropic.Anthropic(api_key=api_key)
    user_message = _build_user_message(title, key_concepts, transcript, speaker_stats)

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                # Кэшируем неизменную инструкцию между запросами.
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = "".join(block.text for block in response.content if block.type == "text")
    logger.info(
        "LLM usage: in=%s out=%s cache_read=%s",
        response.usage.input_tokens,
        response.usage.output_tokens,
        getattr(response.usage, "cache_read_input_tokens", None),
    )

    data = extract_json(raw_text)
    analysis = LLMAnalysis.model_validate(data)

    # Баланс речи считаем сами из реальных длительностей + ролей от модели.
    analysis.teacher_talk_ratio, analysis.student_talk_ratio = _compute_balance(
        analysis.speaker_roles, speaker_stats
    )
    display_labels = _build_display_labels(analysis.speaker_roles, speaker_stats)
    logger.info(
        "Роли спикеров: %s | баланс преп/студ: %.2f/%.2f",
        analysis.speaker_roles,
        analysis.teacher_talk_ratio,
        analysis.student_talk_ratio,
    )
    return analysis, raw_text, display_labels
