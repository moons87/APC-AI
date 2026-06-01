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
