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
