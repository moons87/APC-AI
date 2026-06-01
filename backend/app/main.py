"""FastAPI-приложение «ИИ-наблюдатель урока».

Эндпоинты:
  POST /lessons/upload  — загрузка аудио + тема + ключевые понятия, запуск анализа
  GET  /lessons/{id}    — статус и результат конкретного урока
  GET  /lessons         — список всех уроков

Асинхронность: upload сохраняет файл, создаёт запись (status=pending) и сразу
отвечает lesson_id. Тяжёлая обработка (STT + диаризация + LLM) уходит в
BackgroundTasks. Для синхронной функции FastAPI выполняет её в пуле потоков,
поэтому event loop не блокируется.

NB: для продакшена очередь стоит вынести в Celery/RQ с отдельными воркерами —
тогда обработка переживёт перезапуск API и масштабируется горизонтально.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import List

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models
from .analysis import analyze_transcript
from .database import SessionLocal, get_db, init_db
from .doc_extract import ALLOWED_PLAN_EXT, extract_text
from .plan_check import check_plan
from .schemas import (
    LessonDetail,
    LessonSummary,
    PlanCheckListItem,
    PlanCheckOut,
    UploadResponse,
)
from .transcription import relabel_transcript, transcribe_and_diarize
from .media import ensure_wav

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/data/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Жёсткий лимит размера файла учебного плана. В отличие от аудио, документ-план
# мал, поэтому лимит низкий — это страхует от загрузки в память гигантских
# .xlsx/.pdf (вплоть до zip-bomb) до их разбора.
MAX_PLAN_UPLOAD_MB = int(os.getenv("MAX_PLAN_UPLOAD_MB", "25"))

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

app = FastAPI(title="ИИ-наблюдатель урока", version="0.1.0")

# CORS: фронтенд (Vite) ходит с другого origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# --------------------------------------------------------------------------- #
# Фоновая обработка
# --------------------------------------------------------------------------- #
def process_lesson(lesson_id: int, audio_path: str):
    """Полный пайплайн обработки одного урока. Запускается в фоне."""
    db: Session = SessionLocal()
    try:
        lesson = db.get(models.Lesson, lesson_id)
        if lesson is None:
            logger.error("Урок %s не найден для обработки", lesson_id)
            return

        lesson.status = "processing"
        db.commit()

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

        if not stt["transcript"].strip():
            raise ValueError("Пустой транскрипт — не удалось распознать речь")

        # 2. LLM-анализ. Модель определяет роли спикеров по смыслу речи,
        #    баланс речи считается из реальных длительностей диаризации.
        logger.info("Урок %s: анализ LLM...", lesson_id)
        analysis, raw, display_labels = analyze_transcript(
            title=lesson.title,
            key_concepts=lesson.key_concepts or [],
            transcript=stt["transcript"],
            speaker_stats=stt["speaker_stats"],
        )

        # Переразмечаем транскрипт человекочитаемыми ролями (ПРЕПОДАВАТЕЛЬ/СТУДЕНТ N).
        lesson.transcript = relabel_transcript(stt["transcript"], display_labels)

        # 3. Сохранение результата
        result = models.AnalysisResult(
            lesson_id=lesson.id,
            teacher_talk_ratio=analysis.teacher_talk_ratio,
            student_talk_ratio=analysis.student_talk_ratio,
            total_questions=analysis.total_questions,
            open_questions=analysis.open_questions,
            closed_questions=analysis.closed_questions,
            covered_concepts=analysis.covered_concepts,
            missing_concepts=analysis.missing_concepts,
            structure_present=analysis.structure_present.model_dump(),
            recommendations=analysis.recommendations,
            raw_response=raw,
        )
        db.add(result)
        lesson.status = "done"
        db.commit()
        logger.info("Урок %s: готово", lesson_id)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Урок %s: ошибка обработки", lesson_id)
        db.rollback()
        lesson = db.get(models.Lesson, lesson_id)
        if lesson is not None:
            lesson.status = "error"
            lesson.error_message = str(exc)[:2000]
            db.commit()
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Эндпоинты
# --------------------------------------------------------------------------- #
@app.post("/lessons/upload", response_model=UploadResponse)
async def upload_lesson(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    language: str = Form("ru"),
    key_concepts: str = Form(""),  # JSON-массив ИЛИ строки через перенос/запятую
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if language not in {"kk", "ru"}:
        raise HTTPException(400, "language должен быть 'kk' или 'ru'")

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

    lesson = models.Lesson(
        title=title.strip(),
        language=language,
        key_concepts=concepts,
        audio_filename=safe_name,
        status="pending",
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)

    # Запускаем обработку в фоне — клиент получает ответ сразу.
    background_tasks.add_task(process_lesson, lesson.id, dest_path)

    return UploadResponse(lesson_id=lesson.id, status=lesson.status)


@app.get("/lessons", response_model=List[LessonSummary])
def list_lessons(db: Session = Depends(get_db)):
    return (
        db.query(models.Lesson)
        .order_by(models.Lesson.created_at.desc())
        .all()
    )


@app.get("/lessons/{lesson_id}", response_model=LessonDetail)
def get_lesson(lesson_id: int, db: Session = Depends(get_db)):
    lesson = db.get(models.Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "Урок не найден")
    return lesson


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

    # Если приложен файл — он имеет приоритет над вставленным текстом.
    if file is not None and file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_PLAN_EXT:
            raise HTTPException(
                400,
                f"Неподдерживаемый формат: {ext}. Разрешено: {sorted(ALLOWED_PLAN_EXT)}",
            )
        # Читаем не больше лимита (cap+1, чтобы детектировать превышение),
        # не загружая в память файлы произвольного размера.
        cap = MAX_PLAN_UPLOAD_MB * 1024 * 1024
        raw_bytes = await file.read(cap + 1)
        if len(raw_bytes) > cap:
            raise HTTPException(413, f"Файл больше лимита {MAX_PLAN_UPLOAD_MB} МБ")
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


@app.get("/health")
def health():
    return {"status": "ok"}


def _parse_concepts(raw: str) -> list:
    """Принимает либо JSON-массив, либо текст с понятиями через запятую/перенос."""
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except json.JSONDecodeError:
        pass
    parts = re.split(r"[\n,;]+", raw)
    return [p.strip() for p in parts if p.strip()]
