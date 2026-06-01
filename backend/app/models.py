"""SQLAlchemy-модели: урок и результат его анализа."""
import datetime

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
from sqlalchemy.orm import relationship

from .database import Base


class Lesson(Base):
    """Загруженный урок и метаданные обработки.

    status — конечный автомат: pending -> processing -> done | error.
    """

    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(512), nullable=False)
    language = Column(String(8), default="ru", nullable=False)  # kk | ru
    key_concepts = Column(JSON, default=list, nullable=False)    # list[str]
    audio_filename = Column(String(1024), nullable=False)

    status = Column(String(16), default="pending", nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    transcript = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    # uselist=False — связь один-к-одному с результатом анализа.
    result = relationship(
        "AnalysisResult",
        back_populates="lesson",
        uselist=False,
        cascade="all, delete-orphan",
    )


class AnalysisResult(Base):
    """Структурированный результат LLM-анализа транскрипта."""

    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, unique=True)

    teacher_talk_ratio = Column(Float, nullable=False)
    student_talk_ratio = Column(Float, nullable=False)

    total_questions = Column(Integer, nullable=False)
    open_questions = Column(Integer, nullable=False)
    closed_questions = Column(Integer, nullable=False)

    covered_concepts = Column(JSON, nullable=False)   # list[str]
    missing_concepts = Column(JSON, nullable=False)   # list[str]
    structure_present = Column(JSON, nullable=False)   # {intro, explanation, practice, summary}
    recommendations = Column(JSON, nullable=False)     # list[str]

    raw_response = Column(Text, nullable=True)  # сырой ответ модели для отладки

    lesson = relationship("Lesson", back_populates="result")
