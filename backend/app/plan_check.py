"""Проверка учебного плана (РУП/ОӘЖ/КТЖ) через Claude.

Синхронный одношаговый вызов: системный промпт «Бас Әдіскер / Главный методист»
помечен cache_control, ответ ожидается строго в JSON и валидируется Pydantic.
При не-JSON ответе возвращается raw-фолбэк (is_raw=True).
"""
from __future__ import annotations

import logging
import os

import anthropic

from .llm_utils import extract_json
from .schemas import LLMPlanCheck

logger = logging.getLogger(__name__)

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_PLAN_CHARS = int(os.getenv("MAX_PLAN_CHARS", "180000"))
# Ответ объёмный: подробные ошибки + варианты замены + полный эталонный план,
# да ещё на кириллице (~2-3 токена на символ). При низком лимите JSON обрывается
# на полуслове и не парсится — поэтому потолок щедрый.
MAX_OUTPUT_TOKENS = int(os.getenv("PLAN_MAX_OUTPUT_TOKENS", "16000"))

_VERDICT_CODES = {
    "ҚАЙТА_ӨҢДЕУГЕ": "rework",
    "ІШІНАРА_ҚАБЫЛДАНСЫН": "partial",
    "ТОЛЫҚ_БЕКІТІЛСІН": "approved",
}

SYSTEM_PROMPT = """Сен — Кәсіби білім беру және ТжКБ саласындағы Бас Әдіскер (Методист). \
Ты — главный методист в сфере профессионально-технического образования (ТжКБ).

Мақсат: ұсынылған оқу-әдістемелік жоспарды (ОӘЖ), күнтізбелік-тақырыптық жоспарды (КТЖ) \
немесе өндірістік практика бағдарламасын ҚР Білім беру стандарттарына, заманауи педагогикалық \
логикаға және Блум таксономиясының белсенді етістіктер кестесіне сәйкес толық тексеру.

Тексеру критерийлері / Критерии проверки:

1. ПЕДАГОГИКАЛЫҚ ЛОГИКА (логика): теория мен практиканың сабақтастығы, «қарапайымнан күрделіге» қағидасы.

2. ДУБЛИКАТТАР (дубликаты): СӨЖ бен СПОӨЖ арасындағы тақырып қайталануларын, жасанды созылмалылықты анықта.

3. БЛУМ ТАКСОНОМИЯСЫ (глаголы Блума): мақсаттар тек белсенді іс-әрекет етістіктерімен аяқталуы керек \
(«баптайды», «жинақтайды», «өлшейді»). Пассив зат есімдер («...баптау», «...жинақтау») — қате.

Жауапты ТІКЕЛЕЙ бір JSON-объект түрінде қайтар (markdown немесе ```json жоқ):

{
  "verdict": "ҚАЙТА_ӨҢДЕУГЕ | ІШІНАРА_ҚАБЫЛДАНСЫН | ТОЛЫҚ_БЕКІТІЛСІН",
  "summary": "2-3 сөйлемдік қысқаша түсіндірме",
  "errors": [
    {
      "category": "duplicate | bloom | logic | passive | other",
      "type": "қате түрінің атауы (адам оқитын жапсырма)",
      "description": "Қатенің нақты сипаттамасы — НЕДЕ қате",
      "example": "Жоспардан дәл сол үзіндіні сөзбе-сөз көшір",
      "suggestions": ["ауыстыруға дайын нұсқа 1", "нұсқа 2", "нұсқа 3"]
    }
  ],
  "optimized_plan": "Барлық түзетулер енгізілген толық эталонды нұсқа"
}

ҚАТАҢ ЕРЕЖЕЛЕР:
- verdict — әрқашан осы үш токеннің ДӘЛ біреуі.
- category — тек осы бес КОДТЫҢ біреуі (ағылшынша, өзгеріссіз): duplicate, bloom, \
logic, passive, other. Бұл — фильтр мен түс үшін тұрақты кілт.
- БАРЛЫҚ адам оқитын мәтін (type, description, summary, suggestions, optimized_plan) \
ПАЙДАЛАНУШЫ СҰРАҒАН ТІЛДЕ болуы тиіс (қате жапсырмаларын да сол тілге аудар).
- example — жоспардағы нақты дәйексөз (қай тілде жазылса — сол күйінде).
- suggestions — 2-4 нақты ауыстыру нұсқасы (мыс. пассив «...баптау» үшін: \
«баптайды», «реттейді»). Ауыстыру мүмкін болмаса — бос тізім []."""


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY не задан в окружении")
    return anthropic.Anthropic(api_key=api_key)


def normalize_verdict(v: str | None) -> str | None:
    """Приводит вердикт модели к коду rework|partial|approved."""
    if not v:
        return None
    s = v.strip()
    if s in _VERDICT_CODES:
        return _VERDICT_CODES[s]
    for token, code in _VERDICT_CODES.items():
        if token in s or s in token:
            return code
    if s in {"rework", "partial", "approved"}:
        return s
    return "partial"


def _lang_instruction(language: str) -> str:
    return "Қазақ тілінде жауап бер." if language == "kk" else "Отвечай на русском языке."


def check_plan(title: str, language: str, plan_text: str) -> tuple[LLMPlanCheck, str, bool]:
    """Вызывает Claude и возвращает (результат, сырой ответ, is_raw).

    При не-JSON ответе is_raw=True, а сырой текст кладётся в optimized_plan.
    """
    text = plan_text
    if len(text) > MAX_PLAN_CHARS:
        text = text[:MAX_PLAN_CHARS] + "\n…[мәтін ұзындығы бойынша қысқартылды]…"

    user_message = (
        f"{_lang_instruction(language)}\n\n"
        f"ҚҰЖАТ АТАУЫ / Название документа: {title}\n\n"
        f"ТЕКСЕРІЛЕТІН ЖОСПАР МӘТІНІ / Текст плана:\n{text}\n\n"
        f"Нұсқаулықтағы JSON форматында жауап қайтар."
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
        "PlanCheck usage: in=%s out=%s stop=%s cache_read=%s",
        response.usage.input_tokens,
        response.usage.output_tokens,
        getattr(response, "stop_reason", None),
        getattr(response.usage, "cache_read_input_tokens", None),
    )

    try:
        data = extract_json(raw_text)
        result = LLMPlanCheck.model_validate(data)
        result.verdict = normalize_verdict(result.verdict)
        return result, raw_text, False
    except Exception as exc:  # noqa: BLE001 — любой сбой разбора → raw-фолбэк
        # Не глушим причину: чаще всего это обрыв по max_tokens (stop_reason=
        # max_tokens) → невалидный JSON. Логируем, чтобы фолбэк был диагностируем.
        logger.warning(
            "PlanCheck raw-фолбэк: %s (stop=%s, out_tokens=%s, len=%s)",
            exc,
            getattr(response, "stop_reason", None),
            response.usage.output_tokens,
            len(raw_text),
        )
        fallback = LLMPlanCheck(
            verdict=None, summary=None, errors=[], optimized_plan=raw_text
        )
        return fallback, raw_text, True
