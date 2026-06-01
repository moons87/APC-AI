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
