# Автозаполнение полей урока из плана — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать возможность приложить план урока (файлом docx/pdf/xlsx/txt **или** вставленным текстом), автоматически извлечь из него тему и ключевые понятия через Claude и подставить их в поля формы загрузки урока для проверки и правки.

**Architecture:** Новый синхронный эндпоинт `POST /lessons/plan-extract` переиспользует `doc_extract.extract_text` (для файла) и новый модуль `plan_extract.py` (вызов Claude, парсинг JSON), возвращая `{title, key_concepts}`. Существующий `POST /lessons/upload` и модели БД не меняются — извлечённые поля живут только в форме. Фронтенд добавляет блок «План урока» с кнопкой «Разобрать план», которая зовёт эндпоинт и перезаписывает поля.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Anthropic SDK (бэкенд); React + Vite (фронтенд); pytest (тесты бэкенда).

---

### Task 1: Pydantic-схемы для извлечения полей

**Files:**
- Modify: `backend/app/schemas.py` (добавить в конец файла)
- Test: `backend/app/tests/test_plan_extract.py` (создаётся в Task 2; схемы покрываются там)

- [ ] **Step 1: Добавить схемы в `schemas.py`**

В конец файла `backend/app/schemas.py` добавить:

```python
# --- Автозаполнение полей урока из плана ---
class LLMPlanExtract(BaseModel):
    """Схема ответа Claude при извлечении полей из плана урока."""

    title: str = ""
    key_concepts: List[str] = []


class PlanExtractOut(BaseModel):
    """Ответ POST /lessons/plan-extract — подставляется в форму загрузки урока."""

    title: str = ""
    key_concepts: List[str] = []
```

- [ ] **Step 2: Проверить, что модуль импортируется**

Run: `cd backend && .venv/Scripts/python -c "from app.schemas import LLMPlanExtract, PlanExtractOut; print('ok')"`
Expected: выводит `ok` без ошибок импорта.

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas.py
git commit -m "feat: схемы LLMPlanExtract и PlanExtractOut"
```

---

### Task 2: Модуль `plan_extract.py` (вызов Claude)

**Files:**
- Create: `backend/app/plan_extract.py`
- Test: `backend/app/tests/test_plan_extract.py`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/app/tests/test_plan_extract.py`:

```python
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
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `cd backend && .venv/Scripts/python -m pytest app/tests/test_plan_extract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.plan_extract'`.

- [ ] **Step 3: Создать модуль `backend/app/plan_extract.py`**

```python
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
```

- [ ] **Step 4: Запустить тест — убедиться, что проходит**

Run: `cd backend && .venv/Scripts/python -m pytest app/tests/test_plan_extract.py -v`
Expected: PASS — оба теста зелёные.

- [ ] **Step 5: Commit**

```bash
git add backend/app/plan_extract.py backend/app/tests/test_plan_extract.py
git commit -m "feat: извлечение темы и ключевых понятий из плана через Claude"
```

---

### Task 3: Эндпоинт `POST /lessons/plan-extract`

**Files:**
- Modify: `backend/app/main.py` (импорты + новый эндпоинт)
- Test: `backend/app/tests/test_plan_extract_api.py`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/app/tests/test_plan_extract_api.py`:

```python
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
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `cd backend && .venv/Scripts/python -m pytest app/tests/test_plan_extract_api.py -v`
Expected: FAIL — эндпоинт `/lessons/plan-extract` отдаёт 404 (или ImportError на `extract_plan_fields`).

- [ ] **Step 3: Добавить импорты в `main.py`**

В `backend/app/main.py` после строки `from .plan_check import check_plan` добавить:

```python
from .plan_extract import extract_plan_fields
```

В импорте схем (блок `from .schemas import (...)`) добавить `PlanExtractOut` в список:

```python
from .schemas import (
    LessonDetail,
    LessonSummary,
    PlanCheckListItem,
    PlanCheckOut,
    PlanExtractOut,
    UploadResponse,
)
```

- [ ] **Step 4: Добавить эндпоинт в `main.py`**

Вставить новый эндпоинт сразу ПОСЛЕ функции `get_lesson` (перед секцией «Методист РУП», т.е. перед комментарием `# ---...` и `@app.post("/plans/check"...)`):

```python
@app.post("/lessons/plan-extract", response_model=PlanExtractOut)
async def extract_plan_for_lesson(
    language: str = Form("ru"),
    text: str = Form(""),
    file: UploadFile | None = File(None),
):
    """Разбирает план урока (файл ИЛИ текст) и возвращает тему + ключевые понятия.

    Вспомогательный синхронный разбор для предзаполнения формы загрузки урока.
    Запись в БД не создаётся. Файл (если приложен) имеет приоритет над текстом.
    """
    if language not in {"kk", "ru"}:
        raise HTTPException(400, "language должен быть 'kk' или 'ru'")

    plan_text = (text or "").strip()

    if file is not None and file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_PLAN_EXT:
            raise HTTPException(
                400,
                f"Неподдерживаемый формат: {ext}. Разрешено: {sorted(ALLOWED_PLAN_EXT)}",
            )
        cap = MAX_PLAN_UPLOAD_MB * 1024 * 1024
        raw_bytes = await file.read(cap + 1)
        if len(raw_bytes) > cap:
            raise HTTPException(413, f"Файл больше лимита {MAX_PLAN_UPLOAD_MB} МБ")
        try:
            plan_text = extract_text(file.filename, raw_bytes).strip()
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    if not plan_text:
        raise HTTPException(400, "Нужен текст плана или файл с текстом")

    try:
        result, _raw = extract_plan_fields(plan_text, language)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Разбор плана: ошибка")
        raise HTTPException(502, f"Не удалось разобрать план: {exc}")

    return PlanExtractOut(title=result.title, key_concepts=result.key_concepts)
```

- [ ] **Step 5: Запустить тест — убедиться, что проходит**

Run: `cd backend && .venv/Scripts/python -m pytest app/tests/test_plan_extract_api.py -v`
Expected: PASS — все 5 тестов зелёные.

- [ ] **Step 6: Прогнать весь бэкенд-набор тестов (контракт не сломан)**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: PASS — все тесты, включая существующие `test_plans_api.py` и `test_uploads.py`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/main.py backend/app/tests/test_plan_extract_api.py
git commit -m "feat: эндпоинт /lessons/plan-extract (разбор плана для автозаполнения)"
```

---

### Task 4: API-клиент на фронтенде

**Files:**
- Modify: `frontend/src/api.js`

- [ ] **Step 1: Добавить функцию `extractPlanFields` в `api.js`**

В `frontend/src/api.js` после функции `uploadLesson` (перед `getLesson`) добавить:

```javascript
export async function extractPlanFields({ file, text, language }) {
  const form = new FormData();
  form.append("language", language);
  if (text) form.append("text", text);
  if (file) form.append("file", file);

  const res = await fetch(`${API_URL}/lessons/plan-extract`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Не удалось разобрать план: ${res.status} ${body}`);
  }
  return res.json(); // { title, key_concepts }
}
```

- [ ] **Step 2: Проверить синтаксис сборкой**

Run: `cd frontend && npm run build`
Expected: сборка проходит без ошибок (Vite собирает `dist`).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat(front): API-клиент разбора плана урока"
```

---

### Task 5: Блок «План урока» в форме загрузки

**Files:**
- Modify: `frontend/src/components/UploadForm.jsx`

- [ ] **Step 1: Добавить импорт и состояние**

В `frontend/src/components/UploadForm.jsx` заменить строку импорта:

```javascript
import { uploadLesson } from "../api.js";
```

на:

```javascript
import { extractPlanFields, uploadLesson } from "../api.js";
```

В теле компонента после `const [error, setError] = useState("");` добавить состояние блока плана:

```javascript
  const [planFile, setPlanFile] = useState(null);
  const [planText, setPlanText] = useState("");
  const [parsing, setParsing] = useState(false);
```

- [ ] **Step 2: Добавить обработчик разбора плана**

Перед `const handleSubmit` добавить:

```javascript
  const handleParsePlan = async () => {
    setError("");
    if (!planFile && !planText.trim()) {
      setError("Приложите файл плана или вставьте его текст");
      return;
    }
    setParsing(true);
    try {
      const { title: t, key_concepts } = await extractPlanFields({
        file: planFile,
        text: planText.trim(),
        language,
      });
      if (t) setTitle(t);
      setKeyConcepts((key_concepts || []).join("\n"));
    } catch (err) {
      setError(err.message);
    } finally {
      setParsing(false);
    }
  };
```

- [ ] **Step 3: Добавить разметку блока плана в форму**

В JSX сразу после `<h3>Новый урок</h3>` (перед `<label className="field">` с темой урока) вставить блок:

```jsx
      <div className="field plan-import">
        <span className="plan-import__title">План урока (необязательно)</span>
        <input
          type="file"
          accept=".docx,.pdf,.xlsx,.txt"
          onChange={(e) => setPlanFile(e.target.files[0] || null)}
        />
        <small className="field__hint">docx, pdf, xlsx, txt</small>
        <textarea
          rows={3}
          value={planText}
          onChange={(e) => setPlanText(e.target.value)}
          placeholder="…или вставьте текст плана"
        />
        <button
          type="button"
          className="btn btn--secondary"
          onClick={handleParsePlan}
          disabled={parsing}
        >
          {parsing ? "Разбираю план…" : "Разобрать план → заполнить поля"}
        </button>
      </div>
```

- [ ] **Step 4: Проверить сборку**

Run: `cd frontend && npm run build`
Expected: сборка проходит без ошибок.

- [ ] **Step 5: Ручная проверка в браузере**

Запустить стек (`docker compose up` или dev-режим фронта/бэка). В разделе «Новый урок»:
1. Вставить текст плана в textarea → нажать «Разобрать план» → поля «Тема» и «Ключевые понятия» заполняются.
2. Очистить, приложить файл `.docx`/`.txt` → нажать «Разобрать план» → поля заполняются.
3. Нажать «Разобрать план» с пустыми полями → видна ошибка «Приложите файл плана или вставьте его текст».
4. Отредактировать предзаполненные поля и запустить анализ — урок загружается как обычно.

Expected: все 4 сценария работают; кнопка блокируется на время разбора.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/UploadForm.jsx
git commit -m "feat(front): блок «План урока» с автозаполнением полей"
```

---

### Task 6: Стили блока плана (опционально, по месту)

**Files:**
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Добавить стили блока `.plan-import`**

Найти в `frontend/src/styles.css` существующий блок стилей формы (например `.upload-form`) и рядом добавить. Класс `.btn--secondary` в проекте отсутствует, поэтому определяем и его (приглушённый вариант основной кнопки `.btn`):

```css
.plan-import {
  display: flex;
  flex-direction: column;
  border: 1px dashed var(--border, #d0d5dd);
  border-radius: 8px;
  padding: 12px;
  gap: 8px;
}

.plan-import__title {
  font-weight: 600;
}

.plan-import textarea {
  resize: vertical;
}

.btn--secondary {
  background: transparent;
  color: inherit;
  border: 1px solid var(--border, #d0d5dd);
}
```

- [ ] **Step 2: Проверить сборку и вид в браузере**

Run: `cd frontend && npm run build`
Expected: сборка проходит; блок «План урока» визуально отделён рамкой.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/styles.css
git commit -m "style(front): оформление блока «План урока»"
```

---

## Self-Review

**Spec coverage:**
- Модуль `plan_extract.py` + `extract_plan_fields` → Task 2. ✓
- Эндпоинт `POST /lessons/plan-extract` (file ИЛИ text, приоритет файла, лимиты, 400/413) → Task 3. ✓
- Схемы `LLMPlanExtract`, `PlanExtractOut` → Task 1. ✓
- Без изменений `models.py`/миграций → ни одна задача их не трогает. ✓
- `/lessons/upload` без изменений → подтверждается прогоном тестов в Task 3 Step 6. ✓
- `api.js` `extractPlanFields` → Task 4. ✓
- UI-блок с file + textarea + кнопкой «Разобрать план», перезапись полей, статус, обработка ошибок → Task 5. ✓
- Крайние случаи (пустой ввод, формат, лимит, ошибка модели → 502) → Task 3 (тесты) + Task 5 Step 5 (ручная проверка). ✓
- Тесты `test_plan_extract.py` + тесты эндпоинта (текст/файл/формат/лимит/пусто) → Task 2, Task 3. ✓

**Placeholder scan:** плейсхолдеров нет — весь код приведён целиком.

**Type consistency:** `extract_plan_fields(plan_text, language) -> (LLMPlanExtract, str)` используется в Task 3 с тем же именем и сигнатурой; `PlanExtractOut{title, key_concepts}` совпадает между Task 1, 3 и потребителем в `api.js`/`UploadForm` (`key_concepts`). Имена стейтов фронта (`planFile`, `planText`, `parsing`, `handleParsePlan`) согласованы между Step 1–3 Task 5.

**Примечание по окружению:** команды Python используют `.venv/Scripts/python` (Windows). Если venv-путь иной — подставить актуальный интерпретатор.
