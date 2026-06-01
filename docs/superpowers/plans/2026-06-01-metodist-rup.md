# Методист РУП (проверка учебного плана) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить в приложение «ИИ-наблюдатель урока» отдельный раздел «Методист РУП» — синхронную проверку текстовых учебных планов (вставка текста или загрузка .docx/.pdf/.xlsx/.txt) через Claude, с историей в БД и двуязычным (қаз/рус) интерфейсом.

**Architecture:** Бэкенд FastAPI: новые модули `doc_extract.py` (извлечение текста из файлов), `plan_check.py` (промпт + вызов Claude + парсинг JSON), общий `llm_utils.py` (вынесённый `extract_json`), модель `PlanCheck`, схемы и три эндпоинта (`POST /plans/check`, `GET /plans`, `GET /plans/{id}`) — без фоновой очереди. Фронтенд React: новый раздел через расширение `view`-состояния (без react-router), компоненты формы/результата/истории, новые функции в `api.js`.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, anthropic SDK, python-docx, pypdf, openpyxl, pytest; React (Vite).

**Спека:** `docs/superpowers/specs/2026-06-01-metodist-rup-design.md`

---

## Структура файлов

**Бэкенд (`backend/`):**
- Создать `app/llm_utils.py` — общий `extract_json(text) -> dict`.
- Изменить `app/analysis.py` — использовать `extract_json` из `llm_utils` вместо локального `_extract_json`.
- Создать `app/doc_extract.py` — `extract_text(filename, data) -> str`, `ALLOWED_PLAN_EXT`.
- Создать `app/plan_check.py` — промпт, `check_plan(...)`, `normalize_verdict(...)`.
- Изменить `app/models.py` — модель `PlanCheck`.
- Изменить `app/schemas.py` — `PlanError`, `LLMPlanCheck`, `PlanCheckOut`, `PlanCheckListItem`.
- Изменить `app/main.py` — три эндпоинта `/plans*`.
- Изменить `requirements.txt` — `python-docx`, `pypdf`, `openpyxl`.
- Создать `app/tests/test_llm_utils.py`, `app/tests/test_doc_extract.py`, `app/tests/test_plan_check.py`, `app/tests/test_plans_api.py`.

**Фронтенд (`frontend/src/`):**
- Изменить `api.js` — `checkPlan`, `listPlans`, `getPlan`.
- Создать `components/PlanResult.jsx`, `components/PlanForm.jsx`, `components/PlanCheckPage.jsx`.
- Изменить `App.jsx` — переключатель разделов, вынос экрана урока.
- Изменить `components/Landing.jsx` — вторая кнопка входа.
- Изменить `styles.css` — стили раздела (добавление в конец).

---

## Task 1: Общий хелпер extract_json (рефакторинг)

**Files:**
- Create: `backend/app/llm_utils.py`
- Modify: `backend/app/analysis.py`
- Test: `backend/app/tests/test_llm_utils.py`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/app/tests/test_llm_utils.py`:

```python
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
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `cd backend && python -m pytest app/tests/test_llm_utils.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.llm_utils'`

- [ ] **Step 3: Создать `backend/app/llm_utils.py`**

```python
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
```

- [ ] **Step 4: Запустить тест — убедиться, что проходит**

Run: `cd backend && python -m pytest app/tests/test_llm_utils.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Переключить `analysis.py` на общий хелпер**

В `backend/app/analysis.py` удалить локальную функцию `_extract_json` (строки ~139–167) и добавить импорт. Заменить импортный блок:

```python
from .schemas import LLMAnalysis
```

на:

```python
from .llm_utils import extract_json
from .schemas import LLMAnalysis
```

В функции `analyze_transcript` заменить вызов:

```python
    data = _extract_json(raw_text)
```

на:

```python
    data = extract_json(raw_text)
```

Удалить теперь неиспользуемый `import re` в `analysis.py`, если он больше нигде не используется (проверить: `re` встречается только в удалённой функции — тогда убрать строку `import re`).

- [ ] **Step 6: Запустить тесты бэкенда — ничего не сломалось**

Run: `cd backend && python -m pytest app/tests/test_llm_utils.py app/tests/test_uploads.py app/tests/test_media.py -v`
Expected: PASS (все)

- [ ] **Step 7: Commit**

```bash
git add backend/app/llm_utils.py backend/app/analysis.py backend/app/tests/test_llm_utils.py
git commit -m "refactor: extract_json в общий llm_utils"
```

---

## Task 2: Извлечение текста из файлов (`doc_extract.py`)

**Files:**
- Create: `backend/app/doc_extract.py`
- Modify: `backend/requirements.txt`
- Test: `backend/app/tests/test_doc_extract.py`

- [ ] **Step 1: Добавить зависимости в `requirements.txt`**

В `backend/requirements.txt` после блока LLM (строка с `anthropic==0.42.0`) добавить новый блок:

```
# --- Извлечение текста из документов (Методист РУП) ---
python-docx==1.1.2
pypdf==5.1.0
openpyxl==3.1.5
```

- [ ] **Step 2: Установить зависимости**

Run: `cd backend && python -m pip install python-docx==1.1.2 pypdf==5.1.0 openpyxl==3.1.5`
Expected: успешная установка.

- [ ] **Step 3: Написать падающий тест**

Создать `backend/app/tests/test_doc_extract.py`:

```python
import io

import pytest

from app.doc_extract import ALLOWED_PLAN_EXT, extract_text


def test_txt_decoded():
    data = "Сабақ жоспары\nБөлім 1".encode("utf-8")
    assert "Сабақ жоспары" in extract_text("plan.txt", data)


def test_docx_paragraphs_and_tables():
    import docx

    doc = docx.Document()
    doc.add_paragraph("Кіріспе абзац")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Тема"
    table.rows[0].cells[1].text = "Сварка"
    buf = io.BytesIO()
    doc.save(buf)

    text = extract_text("plan.docx", buf.getvalue())
    assert "Кіріспе абзац" in text
    assert "Сварка" in text


def test_xlsx_cells_joined():
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["№", "Тақырып"])
    ws.append([1, "Дәнекерлеу негіздері"])
    buf = io.BytesIO()
    wb.save(buf)

    text = extract_text("ruP.xlsx", buf.getvalue())
    assert "Тақырып" in text
    assert "Дәнекерлеу негіздері" in text


def test_pdf_pages_joined(monkeypatch):
    class FakePage:
        def __init__(self, t):
            self._t = t

        def extract_text(self):
            return self._t

    class FakeReader:
        def __init__(self, _stream):
            self.pages = [FakePage("Бет 1 мәтіні"), FakePage("Бет 2 мәтіні")]

    monkeypatch.setattr("app.doc_extract.PdfReader", FakeReader)
    text = extract_text("plan.pdf", b"%PDF-fake")
    assert "Бет 1 мәтіні" in text
    assert "Бет 2 мәтіні" in text


def test_unsupported_ext_raises():
    with pytest.raises(ValueError):
        extract_text("plan.rtf", b"data")


def test_allowed_ext_set():
    assert ALLOWED_PLAN_EXT == {".txt", ".docx", ".pdf", ".xlsx"}
```

- [ ] **Step 4: Запустить тест — убедиться, что падает**

Run: `cd backend && python -m pytest app/tests/test_doc_extract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.doc_extract'`

- [ ] **Step 5: Создать `backend/app/doc_extract.py`**

```python
"""Извлечение текста из загруженного учебного плана.

Поддержка: .txt (прямой текст), .docx (python-docx), .pdf (pypdf),
.xlsx (openpyxl — РУП часто оформляют таблицей в Excel).
"""
from __future__ import annotations

import io
import os

import docx
from openpyxl import load_workbook
from pypdf import PdfReader

ALLOWED_PLAN_EXT = {".txt", ".docx", ".pdf", ".xlsx"}


def _from_txt(data: bytes) -> str:
    for enc in ("utf-8", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _from_docx(data: bytes) -> str:
    doc = docx.Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _from_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(p.strip() for p in pages if p.strip())


def _from_xlsx(data: bytes) -> str:
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    lines: list[str] = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def extract_text(filename: str, data: bytes) -> str:
    """Извлекает текст из файла по его расширению.

    Бросает ValueError для неподдерживаемого формата.
    """
    ext = os.path.splitext(filename or "")[1].lower()
    if ext == ".txt":
        return _from_txt(data)
    if ext == ".docx":
        return _from_docx(data)
    if ext == ".pdf":
        return _from_pdf(data)
    if ext == ".xlsx":
        return _from_xlsx(data)
    raise ValueError(
        f"Неподдерживаемый формат: {ext}. Разрешено: {sorted(ALLOWED_PLAN_EXT)}"
    )
```

- [ ] **Step 6: Запустить тест — убедиться, что проходит**

Run: `cd backend && python -m pytest app/tests/test_doc_extract.py -v`
Expected: PASS (6 passed)

- [ ] **Step 7: Commit**

```bash
git add backend/app/doc_extract.py backend/app/tests/test_doc_extract.py backend/requirements.txt
git commit -m "feat: извлечение текста из docx/pdf/xlsx/txt"
```

---

## Task 3: Проверка плана через Claude (`plan_check.py`)

**Files:**
- Create: `backend/app/plan_check.py`
- Test: `backend/app/tests/test_plan_check.py`

> **Порядок выполнения:** этот модуль импортирует `LLMPlanCheck`/`PlanError` из
> `schemas.py`, поэтому **Task 4 Step 1 (определения схем) должен быть выполнен
> ДО этого таска.** При subagent-driven исполнении диспетчеризовать Task 4 раньше
> Task 3 (либо выполнить Task 4 Step 1 первым). Тест мокает Claude и не требует БД.

- [ ] **Step 1: Написать падающий тест**

Создать `backend/app/tests/test_plan_check.py`:

```python
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
            {"type": "Блум қатесі", "description": "Пассив етістік", "example": "...баптау"}
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
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `cd backend && python -m pytest app/tests/test_plan_check.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.plan_check'`

- [ ] **Step 3: Создать `backend/app/plan_check.py`**

> Если `LLMPlanCheck`/`PlanError` ещё не добавлены в `schemas.py`, выполнить Step 1 Task 4 перед этим шагом.

```python
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
      "type": "Дублікат | Блум қатесі | Логика бұзылуы | Пассивті тұжырым",
      "description": "Қатенің сипаттамасы",
      "example": "Жоспардағы нақты мәтін үзіндісі"
    }
  ],
  "optimized_plan": "Барлық түзетулер енгізілген толық эталонды нұсқа"
}

verdict мәні әрқашан осы үш токеннің бірі болуы керек. summary, errors сипаттамалары мен \
optimized_plan пайдаланушы сұраған тілде болуы тиіс."""


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
        max_tokens=4000,
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
        "PlanCheck usage: in=%s out=%s cache_read=%s",
        response.usage.input_tokens,
        response.usage.output_tokens,
        getattr(response.usage, "cache_read_input_tokens", None),
    )

    try:
        data = extract_json(raw_text)
        result = LLMPlanCheck.model_validate(data)
        result.verdict = normalize_verdict(result.verdict)
        return result, raw_text, False
    except Exception:  # noqa: BLE001 — любой сбой разбора → raw-фолбэк
        fallback = LLMPlanCheck(
            verdict=None, summary=None, errors=[], optimized_plan=raw_text
        )
        return fallback, raw_text, True
```

- [ ] **Step 4: Запустить тест — убедиться, что проходит**

Run: `cd backend && python -m pytest app/tests/test_plan_check.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/plan_check.py backend/app/tests/test_plan_check.py
git commit -m "feat: проверка учебного плана через Claude (plan_check)"
```

---

## Task 4: Модель и схемы PlanCheck

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/models.py`

> Step 1 (схемы) можно выполнить раньше Task 3 — `plan_check.py` импортирует `LLMPlanCheck`.

- [ ] **Step 1: Добавить схемы в `schemas.py`**

В конец `backend/app/schemas.py` добавить:

```python
# --- Методист РУП: проверка учебного плана ---
class PlanError(BaseModel):
    type: str
    description: str
    example: Optional[str] = None


class LLMPlanCheck(BaseModel):
    """Схема ответа Claude по проверке плана (валидация перед сохранением)."""

    verdict: Optional[str] = None
    summary: Optional[str] = None
    errors: List[PlanError] = []
    optimized_plan: Optional[str] = None


class PlanCheckListItem(BaseModel):
    """Краткая карточка для истории (GET /plans)."""

    id: int
    title: str
    language: str
    verdict: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PlanCheckOut(PlanCheckListItem):
    """Полный результат проверки (GET /plans/{id}, POST /plans/check)."""

    source_filename: Optional[str] = None
    summary: Optional[str] = None
    errors: List[PlanError] = []
    optimized_plan: Optional[str] = None
    is_raw: bool = False
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Добавить модель в `models.py`**

В конец `backend/app/models.py` (после класса `AnalysisResult`) добавить:

```python
class PlanCheck(Base):
    """Результат проверки учебного плана (Методист РУП).

    status: done | error. Обработка синхронная, поэтому pending/processing нет.
    """

    __tablename__ = "plan_checks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(512), nullable=False)
    language = Column(String(8), default="ru", nullable=False)  # kk | ru
    source_filename = Column(String(1024), nullable=True)
    input_text = Column(Text, nullable=False)

    status = Column(String(16), default="done", nullable=False, index=True)
    error_message = Column(Text, nullable=True)

    verdict = Column(String(32), nullable=True)        # rework | partial | approved
    summary = Column(Text, nullable=True)
    errors = Column(JSON, default=list, nullable=False)  # list[{type, description, example}]
    optimized_plan = Column(Text, nullable=True)
    is_raw = Column(Boolean, default=False, nullable=False)
    raw_response = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
```

Добавить `Boolean` в импорт sqlalchemy в начале файла. Заменить строку импорта:

```python
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
```

на:

```python
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
```

- [ ] **Step 3: Проверить импортируемость (smoke)**

Run: `cd backend && python -c "from app import models, schemas; print(models.PlanCheck.__tablename__, schemas.PlanCheckOut.__name__)"`
Expected: `plan_checks PlanCheckOut`

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas.py backend/app/models.py
git commit -m "feat: модель и схемы PlanCheck"
```

---

## Task 5: Эндпоинты /plans

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/app/tests/test_plans_api.py`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/app/tests/test_plans_api.py`:

```python
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
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `cd backend && python -m pytest app/tests/test_plans_api.py -v`
Expected: FAIL — у `/plans/check` нет роута (404) либо ImportError на `check_plan`.

- [ ] **Step 3: Подключить импорты в `main.py`**

В `backend/app/main.py` после строки `from .analysis import analyze_transcript` добавить:

```python
from .doc_extract import ALLOWED_PLAN_EXT, extract_text
from .plan_check import check_plan
```

И расширить импорт схем. Заменить:

```python
from .schemas import LessonDetail, LessonSummary, UploadResponse
```

на:

```python
from .schemas import (
    LessonDetail,
    LessonSummary,
    PlanCheckListItem,
    PlanCheckOut,
    UploadResponse,
)
```

- [ ] **Step 4: Добавить эндпоинты в `main.py`**

Перед эндпоинтом `@app.get("/health")` добавить:

```python
# --------------------------------------------------------------------------- #
# Методист РУП: проверка учебного плана (синхронно)
# --------------------------------------------------------------------------- #
@app.post("/plans/check", response_model=PlanCheckOut)
async def check_plan_endpoint(
    title: str = Form(...),
    language: str = Form("ru"),
    text: str = Form(""),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    if language not in {"kk", "ru"}:
        raise HTTPException(400, "language должен быть 'kk' или 'ru'")

    source_filename = None
    plan_text = (text or "").strip()

    if file is not None and file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_PLAN_EXT:
            raise HTTPException(
                400,
                f"Неподдерживаемый формат: {ext}. Разрешено: {sorted(ALLOWED_PLAN_EXT)}",
            )
        raw_bytes = await file.read()
        try:
            plan_text = extract_text(file.filename, raw_bytes).strip()
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        source_filename = file.filename

    if not plan_text:
        raise HTTPException(400, "Нужен текст плана или файл с текстом")

    record = models.PlanCheck(
        title=title.strip(),
        language=language,
        source_filename=source_filename,
        input_text=plan_text,
        status="done",
    )
    try:
        result, raw, is_raw = check_plan(title.strip(), language, plan_text)
        record.verdict = result.verdict
        record.summary = result.summary
        record.errors = [e.model_dump() for e in result.errors]
        record.optimized_plan = result.optimized_plan
        record.is_raw = is_raw
        record.raw_response = raw
    except Exception as exc:  # noqa: BLE001
        logger.exception("Проверка плана: ошибка")
        record.status = "error"
        record.error_message = str(exc)[:2000]

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.get("/plans", response_model=List[PlanCheckListItem])
def list_plans(db: Session = Depends(get_db)):
    return (
        db.query(models.PlanCheck)
        .order_by(models.PlanCheck.created_at.desc())
        .all()
    )


@app.get("/plans/{plan_id}", response_model=PlanCheckOut)
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    record = db.get(models.PlanCheck, plan_id)
    if record is None:
        raise HTTPException(404, "Проверка не найдена")
    return record
```

- [ ] **Step 5: Запустить тест — убедиться, что проходит**

Run: `cd backend && python -m pytest app/tests/test_plans_api.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Прогнать весь бэкенд-набор**

Run: `cd backend && python -m pytest app/tests -v`
Expected: PASS (все)

- [ ] **Step 7: Commit**

```bash
git add backend/app/main.py backend/app/tests/test_plans_api.py
git commit -m "feat: эндпоинты /plans (проверка плана + история)"
```

---

## Task 6: API-клиент фронтенда

**Files:**
- Modify: `frontend/src/api.js`

- [ ] **Step 1: Добавить функции в `api.js`**

В конец `frontend/src/api.js` добавить:

```javascript
export async function checkPlan({ title, language, text, file }) {
  const form = new FormData();
  form.append("title", title);
  form.append("language", language);
  if (text) form.append("text", text);
  if (file) form.append("file", file);

  const res = await fetch(`${API_URL}/plans/check`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Ошибка проверки: ${res.status} ${body}`);
  }
  return res.json();
}

export async function listPlans() {
  const res = await fetch(`${API_URL}/plans`);
  if (!res.ok) throw new Error("Не удалось получить список проверок");
  return res.json();
}

export async function getPlan(id) {
  const res = await fetch(`${API_URL}/plans/${id}`);
  if (!res.ok) throw new Error(`Не удалось получить проверку ${id}`);
  return res.json();
}
```

- [ ] **Step 2: Проверка сборки (lint/build)**

Run: `cd frontend && npm run build`
Expected: сборка успешна (новые функции не используются — это нормально).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat(front): API-клиент проверки плана"
```

---

## Task 7: Компонент результата `PlanResult.jsx`

**Files:**
- Create: `frontend/src/components/PlanResult.jsx`

- [ ] **Step 1: Создать `frontend/src/components/PlanResult.jsx`**

```jsx
import { useState } from "react";

const VERDICTS = {
  rework: {
    ru: "Вернуть на доработку",
    kk: "Қайта өңдеуге қайтарылсын",
    icon: "🔴",
    cls: "pc-vc-red",
  },
  partial: {
    ru: "Принять с частичными правками",
    kk: "Ішінара түзетумен қабылдансын",
    icon: "🟡",
    cls: "pc-vc-amber",
  },
  approved: {
    ru: "Полностью утвердить",
    kk: "Толық бекітілсін",
    icon: "🟢",
    cls: "pc-vc-green",
  },
};

function badgeClass(type) {
  const t = (type || "").toLowerCase();
  if (t.includes("дубл") || t.includes("dupl")) return "pc-b-amber";
  if (t.includes("блум") || t.includes("bloom")) return "pc-b-red";
  if (t.includes("логик") || t.includes("logic")) return "pc-b-coral";
  if (t.includes("пассив") || t.includes("passive")) return "pc-b-purple";
  return "pc-b-def";
}

export default function PlanResult({ plan, lang = "ru" }) {
  const [copied, setCopied] = useState(false);

  if (plan.status === "error") {
    return (
      <div className="state card--error">
        <div className="state__emoji">⚠️</div>
        <p className="state__title">Ошибка проверки</p>
        <p className="state__text">{plan.error_message || "Неизвестная ошибка"}</p>
      </div>
    );
  }

  const verdict = plan.verdict ? VERDICTS[plan.verdict] : null;
  const errors = plan.errors || [];

  const copy = async () => {
    if (!plan.optimized_plan) return;
    try {
      await navigator.clipboard.writeText(plan.optimized_plan);
    } catch {
      const el = document.createElement("textarea");
      el.value = plan.optimized_plan;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <div className="pc-results">
      {verdict && (
        <div className={`pc-card ${verdict.cls}`}>
          <div className="pc-card__tag">РЕЗОЛЮЦИЯ</div>
          <div className="pc-verdict">
            <span className="pc-verdict__icon">{verdict.icon}</span>
            <div>
              <div className="pc-verdict__label">{verdict[lang] || verdict.ru}</div>
              {plan.summary && <p className="pc-verdict__sum">{plan.summary}</p>}
            </div>
          </div>
        </div>
      )}

      {!plan.is_raw && (
        <div className="pc-card">
          <div className="pc-card__tag">
            ВЫЯВЛЕННЫЕ ОШИБКИ
            {errors.length > 0 && <span className="pc-err-pill">{errors.length}</span>}
          </div>
          {errors.length === 0 ? (
            <div className="pc-no-errs">✓ Ошибок не выявлено</div>
          ) : (
            <ul className="pc-err-list">
              {errors.map((e, i) => (
                <li key={i} className="pc-err-item">
                  <div className="pc-err-top">
                    <span className="pc-err-n">{i + 1}</span>
                    <span className={`pc-badge ${badgeClass(e.type)}`}>{e.type}</span>
                  </div>
                  {e.description && <p className="pc-err-desc">{e.description}</p>}
                  {e.example && (
                    <>
                      <div className="pc-ex-lbl">Фрагмент:</div>
                      <div className="pc-ex-text">{e.example}</div>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {plan.optimized_plan && (
        <div className="pc-card">
          <div className="pc-card__tag pc-card__tag--row">
            <span>{plan.is_raw ? "ОТВЕТ" : "ЭТАЛОННАЯ ВЕРСИЯ"}</span>
            <button className={`pc-copy${copied ? " pc-copy--ok" : ""}`} onClick={copy}>
              {copied ? "✓ Скопировано" : "📋 Копировать"}
            </button>
          </div>
          <pre className="pc-opt-text">{plan.optimized_plan}</pre>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Проверка сборки**

Run: `cd frontend && npm run build`
Expected: успешно.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/PlanResult.jsx
git commit -m "feat(front): карточки результата проверки плана"
```

---

## Task 8: Компонент формы `PlanForm.jsx`

**Files:**
- Create: `frontend/src/components/PlanForm.jsx`

- [ ] **Step 1: Создать `frontend/src/components/PlanForm.jsx`**

```jsx
import { useState } from "react";
import { checkPlan } from "../api.js";

export default function PlanForm({ onChecked }) {
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState("ru");
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!title.trim()) {
      setError("Укажите название документа");
      return;
    }
    if (!text.trim() && !file) {
      setError("Вставьте текст плана или выберите файл");
      return;
    }
    setBusy(true);
    try {
      const plan = await checkPlan({ title, language, text, file });
      onChecked(plan);
      setText("");
      setFile(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card upload-form" onSubmit={submit}>
      <h3>Проверка учебного плана</h3>

      <label className="field">
        Название документа
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Напр.: РУП «Сварочное дело»"
        />
      </label>

      <label className="field">
        Язык анализа
        <select value={language} onChange={(e) => setLanguage(e.target.value)}>
          <option value="ru">Русский</option>
          <option value="kk">Қазақша</option>
        </select>
      </label>

      <label className="field">
        Текст плана
        <textarea
          className="pc-textarea"
          rows={8}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Вставьте текст ОӘЖ / КТЖ / программы практики…"
        />
        <small className="field__hint">{text.length.toLocaleString()} символов</small>
      </label>

      <label className="field field--file">
        …или файл (.docx, .pdf, .xlsx, .txt)
        <input
          type="file"
          accept=".docx,.pdf,.xlsx,.txt"
          onChange={(e) => setFile(e.target.files[0] || null)}
        />
      </label>

      {error && <p className="form-error">{error}</p>}

      <button type="submit" className="btn" disabled={busy}>
        {busy ? "Методист анализирует…" : "🔍 Проверить"}
      </button>
    </form>
  );
}
```

Классы (`card upload-form`, `field`, `field--file`, `field__hint`, `form-error`, `btn`) совпадают с `UploadForm.jsx`. Дополнительный класс `pc-textarea` добавляется в Task 11.

- [ ] **Step 2: Проверка сборки**

Run: `cd frontend && npm run build`
Expected: успешно.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/PlanForm.jsx
git commit -m "feat(front): форма проверки плана"
```

---

## Task 9: Страница раздела `PlanCheckPage.jsx`

**Files:**
- Create: `frontend/src/components/PlanCheckPage.jsx`

- [ ] **Step 1: Создать `frontend/src/components/PlanCheckPage.jsx`**

```jsx
import { useCallback, useEffect, useState } from "react";
import PlanForm from "./PlanForm.jsx";
import PlanResult from "./PlanResult.jsx";
import { getPlan, listPlans } from "../api.js";

const VERDICT_DOT = {
  rework: "dot--error",
  partial: "dot--processing",
  approved: "dot--done",
};

export default function PlanCheckPage() {
  const [plans, setPlans] = useState([]);
  const [selected, setSelected] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setPlans(await listPlans());
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleChecked = (plan) => {
    setSelected(plan);
    refresh();
  };

  const openPlan = async (id) => {
    try {
      setSelected(await getPlan(id));
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="layout">
      <aside className="sidebar">
        <PlanForm onChecked={handleChecked} />

        <div className="card">
          <h3 className="sidebar__heading">История проверок</h3>
          <ul className="lessons">
            {plans.length === 0 && (
              <li className="lessons__empty">Пока пусто — проверьте первый план.</li>
            )}
            {plans.map((p) => (
              <li
                key={p.id}
                className={
                  "lessons__item" +
                  (selected && p.id === selected.id ? " lessons__item--active" : "")
                }
                onClick={() => openPlan(p.id)}
              >
                <span
                  className={`dot ${VERDICT_DOT[p.verdict] || "dot--pending"}`}
                />
                <span className="lessons__title">{p.title}</span>
                <span className="lessons__status">{p.language}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="content">
        {selected ? (
          <PlanResult plan={selected} lang={selected.language} />
        ) : (
          <div className="state">
            <div className="state__emoji">📋</div>
            <p className="state__title">Здесь появится результат проверки</p>
            <p className="state__text">
              Вставьте текст плана или загрузите файл слева и нажмите «Проверить».
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
```

> Классы `dot--pending/processing/done/error` уже есть в `styles.css` (стили статус-точек уроков) — переиспользуются для цвета вердикта.

- [ ] **Step 2: Проверка сборки**

Run: `cd frontend && npm run build`
Expected: успешно.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/PlanCheckPage.jsx
git commit -m "feat(front): страница раздела «Методист РУП»"
```

---

## Task 10: Навигация (App.jsx + Landing.jsx)

**Files:**
- Modify: `frontend/src/App.jsx` (полная замена содержимого)
- Modify: `frontend/src/components/Landing.jsx`

> Важно: существующий `Landing` навешивает `onClick={onEnter}` напрямую (во многие
> кнопки), поэтому в `onEnter` прилетает объект события. Поэтому в `App` обработчик
> выбирает раздел только если аргумент — строка (`typeof target === "string"`),
> иначе по умолчанию открывает экран урока.

- [ ] **Step 1: Полностью заменить `frontend/src/App.jsx`**

Заменить весь файл на:

```jsx
import { useCallback, useEffect, useRef, useState } from "react";
import UploadForm from "./components/UploadForm.jsx";
import Dashboard from "./components/Dashboard.jsx";
import Landing from "./components/Landing.jsx";
import PlanCheckPage from "./components/PlanCheckPage.jsx";
import { getLesson, listLessons } from "./api.js";

const STATUS_LABELS = {
  pending: "в очереди",
  processing: "обрабатывается",
  done: "готово",
  error: "ошибка",
};

export default function App() {
  const [view, setView] = useState("landing");
  const [lessons, setLessons] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedLesson, setSelectedLesson] = useState(null);
  const pollRef = useRef(null);

  const refreshList = useCallback(async () => {
    try {
      setLessons(await listLessons());
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    refreshList();
  }, [refreshList]);

  // Поллинг выбранного урока, пока он не завершится.
  useEffect(() => {
    if (selectedId == null) return;

    let cancelled = false;
    const tick = async () => {
      try {
        const lesson = await getLesson(selectedId);
        if (cancelled) return;
        setSelectedLesson(lesson);
        refreshList();
        if (lesson.status === "done" || lesson.status === "error") {
          clearInterval(pollRef.current);
        }
      } catch (e) {
        console.error(e);
      }
    };

    tick();
    pollRef.current = setInterval(tick, 3000);
    return () => {
      cancelled = true;
      clearInterval(pollRef.current);
    };
  }, [selectedId, refreshList]);

  const handleUploaded = (lessonId) => {
    setSelectedId(lessonId);
    setSelectedLesson(null);
    refreshList();
  };

  if (view === "landing") {
    return (
      <Landing
        onEnter={(target) =>
          setView(typeof target === "string" ? target : "lesson")
        }
      />
    );
  }

  return (
    <div className="app">
      <button className="app__home" onClick={() => setView("landing")}>
        ← На главную
      </button>

      <nav className="section-tabs">
        <button
          className={"section-tab" + (view === "lesson" ? " section-tab--active" : "")}
          onClick={() => setView("lesson")}
        >
          🎧 Анализ урока
        </button>
        <button
          className={"section-tab" + (view === "plans" ? " section-tab--active" : "")}
          onClick={() => setView("plans")}
        >
          📋 Проверка плана
        </button>
      </nav>

      {view === "plans" ? (
        <PlanCheckPage />
      ) : (
        <LessonSection
          lessons={lessons}
          selectedId={selectedId}
          setSelectedId={setSelectedId}
          selectedLesson={selectedLesson}
          handleUploaded={handleUploaded}
        />
      )}
    </div>
  );
}

function LessonSection({
  lessons,
  selectedId,
  setSelectedId,
  selectedLesson,
  handleUploaded,
}) {
  return (
    <>
      <header className="masthead">
        <span className="masthead__eyebrow">🎧 Анализ урока · ИИ</span>
        <h1 className="masthead__title">ИИ-наблюдатель урока</h1>
        <p className="masthead__sub">
          Загрузите аудио- или видеозапись занятия — система оценит баланс речи,
          вовлечённость, типы вопросов, покрытие плана и структуру урока.
        </p>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <UploadForm onUploaded={handleUploaded} />

          <div className="card">
            <h3 className="sidebar__heading">История уроков</h3>
            <ul className="lessons">
              {lessons.length === 0 && (
                <li className="lessons__empty">Пока пусто — загрузите первый урок.</li>
              )}
              {lessons.map((l) => (
                <li
                  key={l.id}
                  className={
                    "lessons__item" +
                    (l.id === selectedId ? " lessons__item--active" : "")
                  }
                  onClick={() => setSelectedId(l.id)}
                >
                  <span className={`dot dot--${l.status}`} />
                  <span className="lessons__title">{l.title}</span>
                  <span className="lessons__status">
                    {STATUS_LABELS[l.status] || l.status}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </aside>

        <main className="content">
          {selectedLesson ? (
            <LessonView lesson={selectedLesson} />
          ) : (
            <div className="state">
              <div className="state__emoji">📊</div>
              <p className="state__title">Здесь появится дашборд урока</p>
              <p className="state__text">
                Выберите урок в истории слева или загрузите новую запись занятия.
              </p>
            </div>
          )}
        </main>
      </div>
    </>
  );
}

function LessonView({ lesson }) {
  if (lesson.status === "error") {
    return (
      <div className="state card--error">
        <div className="state__emoji">⚠️</div>
        <p className="state__title">Ошибка обработки</p>
        <p className="state__text">{lesson.error_message || "Неизвестная ошибка"}</p>
      </div>
    );
  }

  if (lesson.status !== "done") {
    return (
      <div className="state">
        <div className="spinner" />
        <p className="state__title">{lesson.title}</p>
        <p className="state__text">
          Статус: {STATUS_LABELS[lesson.status] || lesson.status}… Идёт
          транскрибация и анализ — это может занять несколько минут в зависимости
          от длины записи.
        </p>
      </div>
    );
  }

  return <Dashboard lesson={lesson} />;
}
```

- [ ] **Step 2: Проверка сборки**

Run: `cd frontend && npm run build`
Expected: успешно.

- [ ] **Step 3: Добавить вторую кнопку входа в `Landing.jsx`**

В `frontend/src/components/Landing.jsx` найти блок hero-CTA и добавить кнопку
перехода на проверку плана. Заменить:

```jsx
          <div className="lp-cta lp-pop" style={{ "--d": "0.28s" }}>
            <button className="lp-btn lp-btn--lg" onClick={onEnter}>
              Запустить <span className="lp-btn__arrow">→</span>
            </button>
            <button className="lp-btn lp-btn--ghost lp-btn--lg" onClick={scrollTo("how")}>
              Как это работает
            </button>
          </div>
```

на:

```jsx
          <div className="lp-cta lp-pop" style={{ "--d": "0.28s" }}>
            <button className="lp-btn lp-btn--lg" onClick={() => onEnter("lesson")}>
              Запустить <span className="lp-btn__arrow">→</span>
            </button>
            <button
              className="lp-btn lp-btn--ghost lp-btn--lg"
              onClick={() => onEnter("plans")}
            >
              📋 Проверка плана
            </button>
            <button className="lp-btn lp-btn--ghost lp-btn--lg" onClick={scrollTo("how")}>
              Как это работает
            </button>
          </div>
```

Остальные кнопки с `onClick={onEnter}` оставить как есть — благодаря `typeof`-проверке в `App` они откроют экран урока.

- [ ] **Step 4: Проверка сборки**

Run: `cd frontend && npm run build`
Expected: успешно.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/Landing.jsx
git commit -m "feat(front): навигация между разделами «урок» и «план»"
```

---

## Task 11: Стили раздела

**Files:**
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Добавить стили в конец `styles.css`**

В конец `frontend/src/styles.css` добавить (самодостаточный блок, палитра как в оригинале):

```css
/* ===== Методист РУП: раздел проверки плана ===== */
.section-tabs {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin: 0 0 24px;
  flex-wrap: wrap;
}
.section-tab {
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 100px;
  padding: 8px 18px;
  font-size: 0.88rem;
  font-weight: 600;
  color: #4a5568;
  cursor: pointer;
  transition: all 0.15s;
}
.section-tab:hover { border-color: #c3cad6; }
.section-tab--active {
  background: #4f46e5;
  border-color: #4f46e5;
  color: #fff;
}

.pc-textarea { min-height: 180px; resize: vertical; line-height: 1.6; }

.pc-results { display: flex; flex-direction: column; gap: 16px; }
.pc-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.07), 0 4px 12px rgba(0,0,0,0.05);
}
.pc-card__tag {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #a0aec0;
  text-transform: uppercase;
  padding: 12px 20px;
  border-bottom: 1px solid #e2e8f0;
  background: #f7f9fc;
  display: flex;
  align-items: center;
  gap: 10px;
}
.pc-card__tag--row { justify-content: space-between; }

.pc-vc-red   { border-left: 4px solid #dc2626; }
.pc-vc-amber { border-left: 4px solid #d97706; }
.pc-vc-green { border-left: 4px solid #059669; }
.pc-verdict { display: flex; gap: 18px; padding: 22px 24px; align-items: flex-start; }
.pc-verdict__icon { font-size: 2.4rem; line-height: 1; }
.pc-verdict__label { font-size: 1.15rem; font-weight: 700; margin-bottom: 6px; }
.pc-vc-red   .pc-verdict__label { color: #dc2626; }
.pc-vc-amber .pc-verdict__label { color: #d97706; }
.pc-vc-green .pc-verdict__label { color: #059669; }
.pc-verdict__sum { font-size: 0.9rem; color: #4a5568; line-height: 1.6; }

.pc-err-pill {
  background: rgba(220,38,38,0.07);
  color: #dc2626;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 9px;
  border-radius: 100px;
}
.pc-err-list { list-style: none; margin: 0; padding: 0; }
.pc-err-item { padding: 16px 20px; border-bottom: 1px solid #e2e8f0; }
.pc-err-item:last-child { border-bottom: none; }
.pc-err-top { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.pc-err-n {
  width: 22px; height: 22px;
  background: #e2e8f0; color: #4a5568;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.72rem; font-weight: 700;
}
.pc-badge {
  font-size: 0.72rem; font-weight: 700;
  padding: 3px 10px; border-radius: 100px;
}
.pc-b-amber  { background: rgba(217,119,6,0.07);  color: #d97706; }
.pc-b-red    { background: rgba(220,38,38,0.07);  color: #dc2626; }
.pc-b-coral  { background: rgba(234,88,12,0.07);  color: #ea580c; }
.pc-b-purple { background: rgba(124,58,237,0.07); color: #7c3aed; }
.pc-b-def    { background: #f7f9fc; color: #4a5568; }
.pc-err-desc { font-size: 0.88rem; color: #4a5568; margin-bottom: 8px; line-height: 1.55; }
.pc-ex-lbl {
  font-size: 0.7rem; font-weight: 700; color: #a0aec0;
  text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px;
}
.pc-ex-text {
  background: #f0f4f8;
  border-left: 3px solid #667eea;
  border-radius: 0 4px 4px 0;
  padding: 8px 12px;
  font-size: 0.85rem; color: #4a5568; font-style: italic; line-height: 1.5;
}
.pc-no-errs { padding: 26px; text-align: center; color: #059669; font-weight: 500; }

.pc-copy {
  background: transparent;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  color: #4a5568;
  font-size: 0.78rem;
  padding: 4px 12px;
  cursor: pointer;
}
.pc-copy--ok { color: #059669; border-color: #059669; background: rgba(5,150,105,0.07); }
.pc-opt-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 0.88rem;
  color: #4a5568;
  line-height: 1.7;
  padding: 20px;
  max-height: 520px;
  overflow-y: auto;
  margin: 0;
}
```

> Примечание: если в Task 9 классы статус-точек (`dot--error/processing/done/pending`) отсутствуют в `styles.css`, добавить недостающие здесь по образцу существующих `dot--<status>`.

- [ ] **Step 2: Проверка сборки**

Run: `cd frontend && npm run build`
Expected: успешно.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/styles.css
git commit -m "style(front): стили раздела «Методист РУП»"
```

---

## Task 12: Документация (README)

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Дополнить README**

В `README.md` в таблицу API (раздел «🔌 API») добавить строки:

```markdown
| `POST` | `/plans/check` | проверка учебного плана (текст или файл) → результат |
| `GET` | `/plans/{id}` | результат конкретной проверки |
| `GET` | `/plans` | список проверок (история) |
```

И добавить короткий абзац после описания использования урока:

```markdown
### Методист РУП — проверка учебного плана

Раздел «Проверка плана» анализирует текст ОӘЖ / КТЖ / программы практики по
стандартам ТжКБ РК: педагогическая логика, дубликаты, активные глаголы Блума.
Вставьте текст или загрузите файл (`.docx`, `.pdf`, `.xlsx`, `.txt`) — Claude
вернёт резолюцию (🔴/🟡/🟢), список ошибок с примерами и эталонную версию плана.
Обработка синхронная, результаты сохраняются в историю.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: раздел «Методист РУП» в README"
```

---

## Финальная проверка

- [ ] **Прогнать весь бэкенд-набор тестов**

Run: `cd backend && python -m pytest app/tests -v`
Expected: PASS (все).

- [ ] **Собрать фронтенд**

Run: `cd frontend && npm run build`
Expected: успешно.

- [ ] **Ручная проверка (опционально, требует ANTHROPIC_API_KEY и запущенного стека)**

Run: `docker compose up --build`
Проверить: на главной — две кнопки входа; в разделе «Проверка плана» вставка текста → «Проверить» → карточки резолюции/ошибок/эталона; загрузка `.docx`/`.xlsx` работает; история слева открывает прошлый результат.
```
