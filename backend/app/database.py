"""Подключение к PostgreSQL и фабрика сессий SQLAlchemy."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# В docker-compose хост БД называется "db". Локально можно переопределить через env.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@db:5432/lesson_observer",
)

# pool_pre_ping проверяет соединение перед использованием — спасает от "stale"
# коннектов, когда контейнер postgres перезапускался.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    """FastAPI dependency: отдаёт сессию и гарантированно закрывает её."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Создаёт таблицы при старте. Для MVP вместо Alembic-миграций."""
    # Импорт моделей нужен, чтобы они зарегистрировались в Base.metadata.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
