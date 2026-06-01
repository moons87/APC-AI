# Анализ урока по видео — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Разрешить загрузку видеозаписей урока (mp4/mov/mkv/webm), извлекая из них звук и прогоняя по существующему пайплайну анализа.

**Architecture:** Подход A — любой вход (аудио или видео) приводится одним ffmpeg-шагом к 16 кГц моно WAV (новый модуль `app/media.py`), затем неизменённый пайплайн `transcribe_and_diarize → analyze`. Временный WAV удаляется после обработки; оригинал остаётся на диске.

**Tech Stack:** FastAPI, faster-whisper, pyannote.audio, Anthropic SDK, ffmpeg (уже в образе), React/Vite, PostgreSQL, Docker Compose, pytest.

---

## Замечания по окружению

- **Git не инициализирован.** Шаги «Commit» приведены для полноты; если git не используется — пропускайте их (или выполните `git init` один раз).
- **Имя проекта Compose:** `lesson-observer` (берётся из `.env`/`COMPOSE_PROJECT_NAME`). Во всех командах используется `-p lesson-observer`.
- **Тесты гоняются внутри backend-контейнера** через bind-mount исходников (без пересборки на каждый цикл):

  ```powershell
  docker compose -p lesson-observer run --rm -v "${PWD}/backend:/app" -w /app backend pytest app/tests -v
  ```

  Если путь с кириллицей мешает bind-mount — fallback: пересобрать backend и запустить `docker compose -p lesson-observer exec -T backend pytest app/tests -v` (тесты лежат в `app/tests`, попадают в образ через `COPY app ./app`).

## Структура файлов

| Файл | Ответственность | Действие |
|---|---|---|
| `backend/app/media.py` | Привести медиафайл к 16 кГц моно WAV (ffmpeg) | Создать |
| `backend/app/main.py` | Расширения, лимит размера, интеграция `ensure_wav` в фон | Изменить |
| `backend/app/tests/__init__.py` | Пакет тестов | Создать |
| `backend/app/tests/test_media.py` | Тесты `ensure_wav` | Создать |
| `backend/app/tests/test_uploads.py` | Тесты `_check_ext`, `_copy_capped` | Создать |
| `backend/requirements.txt` | Добавить `pytest` | Изменить |
| `frontend/src/components/UploadForm.jsx` | `accept`, подсказка, клиентская проверка размера | Изменить |
| `.env.example` | `MAX_UPLOAD_MB` | Изменить |
| `docker-compose.yml` | Проброс `MAX_UPLOAD_MB` в backend | Изменить |
| `README.md` | Форматы + лимит | Изменить |

---

## Task 1: Тестовый каркас (pytest)

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/tests/__init__.py`

- [ ] **Step 1: Добавить pytest в зависимости**

В `backend/requirements.txt` в конец добавить:

```
# --- Тесты ---
pytest==8.3.4
```

- [ ] **Step 2: Создать пакет тестов**

Создать `backend/app/tests/__init__.py` (пустой файл).

- [ ] **Step 3: Пересобрать backend (поставить pytest в образ)**

Run:
```powershell
docker compose -p lesson-observer up --build -d backend
```
Expected: `Container lesson-observer-backend-1 Started`.

- [ ] **Step 4: Проверить, что pytest запускается**

Run:
```powershell
docker compose -p lesson-observer run --rm -v "${PWD}/backend:/app" -w /app backend pytest app/tests -v
```
Expected: `no tests ran` (каталог пуст) — это нормально, важно, что pytest найден и не падает с ошибкой импорта.

- [ ] **Step 5: Commit (если используете git)**

```bash
git add backend/requirements.txt backend/app/tests/__init__.py
git commit -m "test: add pytest scaffolding for backend"
```

---

## Task 2: Модуль `media.ensure_wav`

**Files:**
- Create: `backend/app/media.py`
- Test: `backend/app/tests/test_media.py`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/app/tests/test_media.py`:

```python
import os
import subprocess
import wave

import pytest

from app.media import ensure_wav


def _make_video_with_audio(path: str) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
            "-shortest", path,
        ],
        check=True,
        capture_output=True,
    )


def _make_video_without_audio(path: str) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
            path,
        ],
        check=True,
        capture_output=True,
    )


def test_ensure_wav_extracts_mono_16k(tmp_path):
    src = str(tmp_path / "clip.mp4")
    _make_video_with_audio(src)
    out = ensure_wav(src)
    try:
        assert os.path.getsize(out) > 0
        with wave.open(out, "rb") as w:
            assert w.getnchannels() == 1
            assert w.getframerate() == 16000
    finally:
        os.remove(out)


def test_ensure_wav_raises_when_no_audio(tmp_path):
    src = str(tmp_path / "silent.mp4")
    _make_video_without_audio(src)
    with pytest.raises(RuntimeError):
        ensure_wav(src)
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run:
```powershell
docker compose -p lesson-observer run --rm -v "${PWD}/backend:/app" -w /app backend pytest app/tests/test_media.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.media'`.

- [ ] **Step 3: Реализовать `ensure_wav`**

Создать `backend/app/media.py`:

```python
"""Приведение медиафайла (аудио или видео) к нормализованному WAV.

Единственная задача модуля — извлечь/перекодировать звуковую дорожку входного
файла в 16 кГц моно WAV через ffmpeg. Видеопоток отбрасывается (-vn). Whisper и
pyannote дальше работают с этим WAV (см. transcription.py).
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)


def ensure_wav(src_path: str) -> str:
    """Конвертирует src_path в 16 кГц моно WAV, возвращает путь к временному файлу.

    Подходит и для аудио, и для видео: ffmpeg сам выбирает аудиодорожку, -vn
    отбрасывает видео. Вызывающий ОБЯЗАН удалить возвращённый файл после работы.

    Бросает RuntimeError, если ffmpeg завершился с ошибкой или результат пуст
    (например, в видео нет звуковой дорожки или файл повреждён).
    """
    fd, out_path = tempfile.mkstemp(suffix=".wav", prefix="lesson_audio_")
    os.close(fd)
    cmd = [
        "ffmpeg", "-y",
        "-i", src_path,
        "-vn",          # отбросить видеопоток
        "-ac", "1",     # моно
        "-ar", "16000", # 16 кГц
        "-f", "wav",
        out_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        if os.path.exists(out_path):
            os.remove(out_path)
        tail = (proc.stderr or "")[-500:]
        raise RuntimeError(
            f"Не удалось извлечь аудио из файла: ffmpeg rc={proc.returncode}. {tail}"
        )
    logger.info("ensure_wav: %s -> %s (%d байт)", src_path, out_path, os.path.getsize(out_path))
    return out_path
```

- [ ] **Step 4: Запустить тест — убедиться, что проходит**

Run:
```powershell
docker compose -p lesson-observer run --rm -v "${PWD}/backend:/app" -w /app backend pytest app/tests/test_media.py -v
```
Expected: PASS (2 passed).

- [ ] **Step 5: Commit (если используете git)**

```bash
git add backend/app/media.py backend/app/tests/test_media.py
git commit -m "feat: add ensure_wav media normalization (audio/video -> 16k mono wav)"
```

---

## Task 3: Валидация расширений и лимит размера (`_check_ext`, `_copy_capped`)

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/app/tests/test_uploads.py`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/app/tests/test_uploads.py`:

```python
import io

import pytest
from fastapi import HTTPException

from app.main import ALLOWED_EXT, FileTooLargeError, _check_ext, _copy_capped


def test_check_ext_accepts_video():
    assert _check_ext("lesson.mp4") == ".mp4"
    assert _check_ext("LESSON.MOV") == ".mov"
    assert ".webm" in ALLOWED_EXT and ".mkv" in ALLOWED_EXT


def test_check_ext_accepts_audio():
    assert _check_ext("rec.mp3") == ".mp3"


def test_check_ext_rejects_unknown():
    with pytest.raises(HTTPException):
        _check_ext("notes.txt")


def test_copy_capped_under_limit():
    src = io.BytesIO(b"x" * 100)
    dst = io.BytesIO()
    total = _copy_capped(src, dst, max_bytes=1000)
    assert total == 100
    assert dst.getvalue() == b"x" * 100


def test_copy_capped_over_limit():
    src = io.BytesIO(b"x" * 2000)
    dst = io.BytesIO()
    with pytest.raises(FileTooLargeError):
        _copy_capped(src, dst, max_bytes=1000)
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run:
```powershell
docker compose -p lesson-observer run --rm -v "${PWD}/backend:/app" -w /app backend pytest app/tests/test_uploads.py -v
```
Expected: FAIL — `ImportError: cannot import name 'FileTooLargeError'` (и др.).

- [ ] **Step 3: Добавить константы и хелперы в `main.py`**

В `backend/app/main.py` найти строку:

```python
ALLOWED_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
```

и заменить её на:

```python
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}
ALLOWED_EXT = AUDIO_EXT | VIDEO_EXT

# Мягкий лимит размера загружаемого файла (видео бывают крупными).
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "2048"))


class FileTooLargeError(Exception):
    """Загруженный файл превысил MAX_UPLOAD_MB."""


def _check_ext(filename: str) -> str:
    """Проверяет расширение, возвращает его в нижнем регистре или бросает 400."""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            400, f"Неподдерживаемый формат: {ext}. Разрешено: {sorted(ALLOWED_EXT)}"
        )
    return ext


def _copy_capped(src, dst, max_bytes: int, chunk: int = 1024 * 1024) -> int:
    """Потоково копирует src→dst, обрывая при превышении max_bytes.

    Бросает FileTooLargeError, как только суммарный объём превысит лимит, — чтобы
    не записывать на диск гигабайты сверх разрешённого. Возвращает число байт.
    """
    total = 0
    while True:
        buf = src.read(chunk)
        if not buf:
            break
        total += len(buf)
        if total > max_bytes:
            raise FileTooLargeError(total)
        dst.write(buf)
    return total
```

- [ ] **Step 4: Запустить тест — убедиться, что проходит**

Run:
```powershell
docker compose -p lesson-observer run --rm -v "${PWD}/backend:/app" -w /app backend pytest app/tests/test_uploads.py -v
```
Expected: PASS (5 passed).

- [ ] **Step 5: Commit (если используете git)**

```bash
git add backend/app/main.py backend/app/tests/test_uploads.py
git commit -m "feat: add video extensions and upload size cap helpers"
```

---

## Task 4: Подключить хелперы в эндпоинт загрузки

**Files:**
- Modify: `backend/app/main.py` (тело `upload_lesson`)

- [ ] **Step 1: Заменить проверку расширения и сохранение файла**

В `backend/app/main.py` в функции `upload_lesson` найти блок:

```python
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Неподдерживаемый формат: {ext}. Разрешено: {sorted(ALLOWED_EXT)}")

    concepts = _parse_concepts(key_concepts)

    # Сохраняем файл с уникальным именем, чтобы не было коллизий.
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(dest_path, "wb") as out:
        shutil.copyfileobj(file.file, out)
```

и заменить на:

```python
    ext = _check_ext(file.filename)

    concepts = _parse_concepts(key_concepts)

    # Сохраняем файл с уникальным именем, обрывая запись при превышении лимита.
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(UPLOAD_DIR, safe_name)
    try:
        with open(dest_path, "wb") as out:
            _copy_capped(file.file, out, MAX_UPLOAD_MB * 1024 * 1024)
    except FileTooLargeError:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise HTTPException(413, f"Файл больше лимита {MAX_UPLOAD_MB} МБ")
```

- [ ] **Step 2: Убрать неиспользуемый импорт `shutil` (если больше не используется)**

Проверить `backend/app/main.py` на другие употребления `shutil`. Если их нет — удалить строку `import shutil` из блока импортов.

Run (проверка):
```powershell
docker compose -p lesson-observer run --rm -v "${PWD}/backend:/app" -w /app backend python -c "import app.main; print('import OK')"
```
Expected: `import OK`.

- [ ] **Step 3: Commit (если используете git)**

```bash
git add backend/app/main.py
git commit -m "feat: validate extension and cap upload size in upload endpoint"
```

---

## Task 5: Интегрировать `ensure_wav` в фоновую обработку

**Files:**
- Modify: `backend/app/main.py` (импорт + `process_lesson`)

- [ ] **Step 1: Добавить импорт `ensure_wav`**

В `backend/app/main.py` найти:

```python
from .transcription import relabel_transcript, transcribe_and_diarize
```

и добавить ниже:

```python
from .media import ensure_wav
```

- [ ] **Step 2: Вставить шаг извлечения аудио в `process_lesson`**

В `process_lesson` найти блок:

```python
        # 1. Транскрибация + диаризация
        logger.info("Урок %s: транскрибация...", lesson_id)
        stt = transcribe_and_diarize(audio_path, language=lesson.language)
        lesson.transcript = stt["transcript"]
        db.commit()
```

и заменить на:

```python
        # 1. Привести вход (аудио или видео) к WAV, затем STT + диаризация.
        #    Временный WAV удаляем в любом случае; оригинал остаётся на диске.
        logger.info("Урок %s: извлечение аудио...", lesson_id)
        wav_path = ensure_wav(audio_path)
        try:
            logger.info("Урок %s: транскрибация...", lesson_id)
            stt = transcribe_and_diarize(wav_path, language=lesson.language)
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)
        lesson.transcript = stt["transcript"]
        db.commit()
```

- [ ] **Step 3: Проверить импорт модуля**

Run:
```powershell
docker compose -p lesson-observer run --rm -v "${PWD}/backend:/app" -w /app backend python -c "import app.main; print('import OK')"
```
Expected: `import OK`.

- [ ] **Step 4: Прогнать весь backend-тестсьют**

Run:
```powershell
docker compose -p lesson-observer run --rm -v "${PWD}/backend:/app" -w /app backend pytest app/tests -v
```
Expected: PASS (7 passed).

- [ ] **Step 5: Commit (если используете git)**

```bash
git add backend/app/main.py
git commit -m "feat: extract audio to wav before transcription in background task"
```

---

## Task 6: Фронтенд — приём видео в форме загрузки

**Files:**
- Modify: `frontend/src/components/UploadForm.jsx`

- [ ] **Step 1: Добавить константу лимита и клиентскую проверку размера**

В `frontend/src/components/UploadForm.jsx` сразу после строки `import { uploadLesson } from "../api.js";` добавить:

```jsx
const MAX_UPLOAD_MB = 2048;
```

В `handleSubmit` найти:

```jsx
    if (!file) {
      setError("Выберите аудиофайл (.mp3 / .wav)");
      return;
    }
```

и заменить на:

```jsx
    if (!file) {
      setError("Выберите аудио- или видеофайл урока");
      return;
    }
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setError(`Файл больше ${MAX_UPLOAD_MB} МБ`);
      return;
    }
```

- [ ] **Step 2: Обновить поле выбора файла (accept + подсказка)**

Найти блок:

```jsx
      <label>
        Аудиофайл (.mp3 / .wav)
        <input
          type="file"
          accept=".mp3,.wav,.m4a,.ogg,.flac,audio/*"
          onChange={(e) => setFile(e.target.files[0] || null)}
        />
      </label>
```

и заменить на:

```jsx
      <label>
        Аудио или видео урока
        <input
          type="file"
          accept=".mp3,.wav,.m4a,.ogg,.flac,audio/*,.mp4,.mov,.mkv,.webm,video/*"
          onChange={(e) => setFile(e.target.files[0] || null)}
        />
        <small>
          Аудио: mp3, wav, m4a, ogg, flac. Видео: mp4, mov, mkv, webm. До 2 ГБ.
        </small>
      </label>
```

- [ ] **Step 3: Проверить сборку фронтенда**

Run:
```powershell
docker compose -p lesson-observer up --build -d frontend
```
Expected: `Container lesson-observer-frontend-1 Started` без ошибок сборки Vite.

- [ ] **Step 4: Commit (если используете git)**

```bash
git add frontend/src/components/UploadForm.jsx
git commit -m "feat: accept video files and client-side size check in upload form"
```

---

## Task 7: Конфигурация и документация

**Files:**
- Modify: `.env.example`, `docker-compose.yml`, `README.md`

- [ ] **Step 1: Добавить `MAX_UPLOAD_MB` в `.env.example`**

В `.env.example` в конец (рядом с прочими параметрами) добавить:

```
# Мягкий лимит размера загружаемого файла в МБ (видео бывают крупными).
MAX_UPLOAD_MB=2048
```

- [ ] **Step 2: Пробросить `MAX_UPLOAD_MB` в backend в `docker-compose.yml`**

В `docker-compose.yml` в `services.backend.environment` добавить строку (рядом с прочими, например после `CORS_ORIGINS`):

```yaml
      MAX_UPLOAD_MB: ${MAX_UPLOAD_MB:-2048}
```

- [ ] **Step 3: Обновить README**

В `README.md` в разделе про использование/форматы указать, что принимаются и аудио (`.mp3`, `.wav`, `.m4a`, `.ogg`, `.flac`), и видео (`.mp4`, `.mov`, `.mkv`, `.webm`); из видео берётся только звуковая дорожка; действует лимит размера `MAX_UPLOAD_MB` (по умолчанию 2048 МБ). В таблицу переменных окружения добавить строку:

```
| `MAX_UPLOAD_MB` | `2048` | мягкий лимит размера загружаемого файла, МБ |
```

- [ ] **Step 4: Применить новую переменную (перезапуск backend)**

Run:
```powershell
docker compose -p lesson-observer up -d backend
```
Expected: backend перезапущен с переменной `MAX_UPLOAD_MB`.

- [ ] **Step 5: Commit (если используете git)**

```bash
git add .env.example docker-compose.yml README.md
git commit -m "docs: document video support and MAX_UPLOAD_MB"
```

---

## Task 8: Сквозная проверка на реальном видео

**Files:** нет (ручная проверка).

- [ ] **Step 1: Сгенерировать короткий тестовый видеоклип со звуком**

Run (создаёт 3-секундный mp4 с тоном):
```powershell
docker compose -p lesson-observer run --rm -v "${PWD}:/host" -w /host backend ffmpeg -y -f lavfi -i sine=frequency=300:duration=3 -f lavfi -i color=c=black:s=128x128:d=3 -shortest test_clip.mp4
```
Expected: в корне проекта появился `test_clip.mp4`.

- [ ] **Step 2: Загрузить видео через API и дождаться обработки**

Run:
```powershell
curl.exe -s -F "title=Тест видео" -F "language=ru" -F "key_concepts=" -F "file=@test_clip.mp4" http://localhost:8000/lessons/upload
```
Затем опросить статус (подставить id из ответа):
```powershell
curl.exe -s http://localhost:8000/lessons/<id>
```
Expected: статус проходит `pending → processing → done` (либо `error` с понятным сообщением, если тон не распознался как речь — для пустого транскрипта это ожидаемо). Главное: видео ПРИНЯЛОСЬ, аудио извлеклось, пайплайн отработал без падения.

- [ ] **Step 3: Проверить очистку временного WAV**

Run:
```powershell
docker compose -p lesson-observer exec -T backend sh -c "ls -1 /tmp/lesson_audio_*.wav 2>/dev/null | wc -l"
```
Expected: `0` — временные WAV не накапливаются.

- [ ] **Step 4: Проверить лимит размера (необязательно)**

Временно выставить крошечный лимит и убедиться в `413`:
```powershell
docker compose -p lesson-observer run --rm -e MAX_UPLOAD_MB=0 -v "${PWD}:/host" -w /host -p 8001:8000 backend sh -c "uvicorn app.main:app --host 0.0.0.0 --port 8000 & sleep 4; curl -s -o /dev/null -w '%{http_code}' -F 'title=x' -F 'file=@test_clip.mp4' http://localhost:8000/lessons/upload"
```
Expected: код ответа `413`. (Это проверка «на лету»; основной сервис не трогается.)

- [ ] **Step 5: Удалить тестовый клип**

Run:
```powershell
Remove-Item test_clip.mp4
```

---

## Self-Review (выполнено автором плана)

- **Покрытие спеки:** только-звук-из-видео (Task 2,5), форматы mp4/mov/mkv/webm (Task 3,6), лимит ~2ГБ конфигурируемый (Task 3,4,7), Подход A нормализации в WAV (Task 2,5), оригиналы остаются + temp WAV удаляется (Task 5), фронт accept+подсказка (Task 6), .env/compose/README (Task 7), pytest на ensure_wav/лимит/расширения (Task 2,3). Обработка ошибок: 400 (Task 3), 413 (Task 3,4), ошибка извлечения → status=error через существующий try/except (Task 5). Все пункты покрыты.
- **Плейсхолдеры:** отсутствуют — весь код приведён целиком.
- **Согласованность типов:** `ensure_wav(str)->str`, `_check_ext(str)->str`, `_copy_capped(src,dst,int)->int`, `FileTooLargeError` — имена совпадают во всех задачах и тестах.
