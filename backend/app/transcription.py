"""Транскрибация (faster-whisper) + диаризация (pyannote.audio).

Итог работы модуля — текстовый транскрипт с НЕЙТРАЛЬНЫМИ ярлыками спикеров:

    [00:12] [СПИКЕР 1] Откройте учебник на странице сорок.
    [00:18] [СПИКЕР 2] А какое упражнение?

и словарь с точной длительностью речи по каждому спикеру (для расчёта баланса).

Дизайн-решения:
- faster-whisper с VAD-фильтром сам режет длинное аудио на сегменты по паузам,
  поэтому ручной чанкинг для STT не нужен — память не растёт линейно с длиной.
- Диаризация и распознавание выполняются независимо, затем сегменты текста
  сопоставляются спикерам по максимальному перекрытию таймкодов.
- Роли (преподаватель/студент) ЗДЕСЬ НЕ назначаются. Спикеры получают нейтральные
  ярлыки «СПИКЕР N»; кто из них преподаватель, а кто студент, определяет LLM по
  смыслу речи (analysis.py), после чего транскрипт переразмечается ролями через
  relabel_transcript(). Это надёжнее старой эвристики «дольше всех говорит =
  преподаватель», которая путалась на коротких отрезках.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "medium")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
# int8 — компромисс скорость/память на CPU. На GPU имеет смысл float16.
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
HF_TOKEN = os.getenv("HF_TOKEN")  # токен HuggingFace для pyannote
DIARIZATION_MODEL = os.getenv("DIARIZATION_MODEL", "pyannote/speaker-diarization-3.1")

# Кэшируем тяжёлые модели на уровне процесса — грузим один раз.
_whisper_model = None
_diarization_pipeline = None


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: str = "SPEAKER_00"

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        logger.info("Загружаю Whisper '%s' (%s/%s)", WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE)
        _whisper_model = WhisperModel(
            WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE
        )
    return _whisper_model


def _get_diarization():
    """Возвращает pyannote-пайплайн или None, если он недоступен.

    Диаризация требует HF_TOKEN и принятых условий модели на HuggingFace.
    Если чего-то нет — не падаем, а работаем без разделения говорящих.
    """
    global _diarization_pipeline
    if _diarization_pipeline is not None:
        return _diarization_pipeline
    if not HF_TOKEN:
        logger.warning("HF_TOKEN не задан — диаризация отключена, все реплики в одном спикере")
        return None
    try:
        from pyannote.audio import Pipeline

        logger.info("Загружаю пайплайн диаризации '%s'", DIARIZATION_MODEL)
        _diarization_pipeline = Pipeline.from_pretrained(DIARIZATION_MODEL, use_auth_token=HF_TOKEN)
        return _diarization_pipeline
    except Exception as exc:  # noqa: BLE001
        logger.exception("Не удалось загрузить диаризацию: %s", exc)
        return None


def _transcribe(audio_path: str, language: str) -> List[Segment]:
    model = _get_whisper()
    segments_iter, info = model.transcribe(
        audio_path,
        language=language,        # "kk" или "ru" — поддержка казахского и русского
        vad_filter=True,          # отрезаем тишину, режем длинное аудио по паузам
        vad_parameters={"min_silence_duration_ms": 500},
        beam_size=5,
    )
    logger.info("Whisper: язык=%s, p=%.2f", info.language, info.language_probability)
    segments = [
        Segment(start=s.start, end=s.end, text=s.text.strip())
        for s in segments_iter
        if s.text and s.text.strip()
    ]
    return segments


def _diarize(audio_path: str) -> Optional[list]:
    """Возвращает список (start, end, speaker) либо None."""
    pipeline = _get_diarization()
    if pipeline is None:
        return None
    try:
        diarization = pipeline(audio_path)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ошибка диаризации, продолжаю без неё: %s", exc)
        return None
    turns = [
        (turn.start, turn.end, speaker)
        for turn, _, speaker in diarization.itertracks(yield_label=True)
    ]
    return turns


def _assign_speakers(segments: List[Segment], turns: Optional[list]) -> None:
    """Проставляет каждому текстовому сегменту спикера по максимальному перекрытию."""
    if not turns:
        return
    for seg in segments:
        best_speaker = seg.speaker
        best_overlap = 0.0
        for t_start, t_end, speaker in turns:
            overlap = min(seg.end, t_end) - max(seg.start, t_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = speaker
        seg.speaker = best_speaker


def _label_speakers(segments: List[Segment]) -> dict:
    """Назначает спикерам НЕЙТРАЛЬНЫЕ ярлыки «СПИКЕР 1..N» по убыванию времени речи.

    Важно: роли (преподаватель/студент) здесь НЕ угадываются по времени. Раньше
    «самый говорливый = преподаватель» давало ошибки на коротких отрезках, где
    дольше всех случайно говорил студент. Теперь роль определяет LLM по СМЫСЛУ
    речи (см. analysis.py), а нейтральные ярлыки лишь стабильно идентифицируют
    говорящих и несут точные длительности из диаризации.
    """
    talk_time: dict = {}
    for seg in segments:
        talk_time[seg.speaker] = talk_time.get(seg.speaker, 0.0) + seg.duration
    if not talk_time:
        return {}

    # Сортируем спикеров по убыванию времени речи — для детерминированной нумерации.
    ordered = sorted(talk_time.items(), key=lambda kv: kv[1], reverse=True)
    return {speaker: f"СПИКЕР {i + 1}" for i, (speaker, _) in enumerate(ordered)}


def relabel_transcript(transcript: str, display_labels: dict) -> str:
    """Заменяет нейтральные «[СПИКЕР N]» на человекочитаемые роли для отображения.

    display_labels: {"СПИКЕР 1": "ПРЕПОДАВАТЕЛЬ", "СПИКЕР 2": "СТУДЕНТ 1", ...}
    Роли приходят из LLM-анализа (analysis.py). Если карты нет — возвращаем как есть.
    """
    if not display_labels:
        return transcript

    def _repl(m: "re.Match") -> str:
        label = m.group(1)
        return f"[{display_labels.get(label, label)}]"

    return re.sub(r"\[(СПИКЕР \d+)\]", _repl, transcript)


def _fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def transcribe_and_diarize(audio_path: str, language: str = "ru") -> dict:
    """Главная точка входа модуля.

    Возвращает:
        {
          "transcript": str,              # размеченный текст для LLM/хранения
          "speaker_stats": {role: sec},   # суммарное время речи по ролям
          "total_duration": float,
        }
    """
    segments = _transcribe(audio_path, language)
    if not segments:
        return {"transcript": "", "speaker_stats": {}, "total_duration": 0.0}

    turns = _diarize(audio_path)
    _assign_speakers(segments, turns)
    label_map = _label_speakers(segments)

    lines = []
    speaker_stats: dict = {}
    for seg in segments:
        label = label_map.get(seg.speaker, "СПИКЕР 1")
        speaker_stats[label] = speaker_stats.get(label, 0.0) + seg.duration
        lines.append(f"[{_fmt_ts(seg.start)}] [{label}] {seg.text}")

    total = sum(seg.duration for seg in segments)
    return {
        "transcript": "\n".join(lines),
        "speaker_stats": speaker_stats,
        "total_duration": total,
    }
