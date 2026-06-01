"""Pydantic-схемы для валидации запросов и сериализации ответов API."""
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class StructurePresent(BaseModel):
    intro: bool = False
    explanation: bool = False
    practice: bool = False
    summary: bool = False


class AnalysisResultOut(BaseModel):
    teacher_talk_ratio: float
    student_talk_ratio: float
    total_questions: int
    open_questions: int
    closed_questions: int
    covered_concepts: List[str]
    missing_concepts: List[str]
    structure_present: StructurePresent
    recommendations: List[str]

    model_config = {"from_attributes": True}


class LessonSummary(BaseModel):
    """Краткая карточка для списка уроков (GET /lessons)."""

    id: int
    title: str
    language: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LessonDetail(LessonSummary):
    """Полные данные урока (GET /lessons/{id})."""

    key_concepts: List[str]
    error_message: Optional[str] = None
    transcript: Optional[str] = None
    result: Optional[AnalysisResultOut] = None

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    lesson_id: int
    status: str


# Схема, которую мы ожидаем получить от LLM. Используется для валидации
# распарсенного JSON перед сохранением в БД.
class LLMAnalysis(BaseModel):
    # Роли спикеров модель определяет ПО СМЫСЛУ речи: ярлык -> "teacher" | "student".
    # Ключи — нейтральные ярлыки из транскрипта ("СПИКЕР 1", "СПИКЕР 2", ...).
    speaker_roles: Dict[str, str] = {}
    # Баланс речи НЕ приходит от модели: он считается в коде из реальных
    # длительностей диаризации и speaker_roles, а затем проставляется в эти поля.
    teacher_talk_ratio: float = Field(default=0.0, ge=0, le=1)
    student_talk_ratio: float = Field(default=0.0, ge=0, le=1)
    total_questions: int = Field(ge=0)
    open_questions: int = Field(ge=0)
    closed_questions: int = Field(ge=0)
    covered_concepts: List[str] = []
    missing_concepts: List[str] = []
    structure_present: StructurePresent = StructurePresent()
    recommendations: List[str] = []
