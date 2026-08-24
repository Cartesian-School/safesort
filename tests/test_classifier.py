"""Tests for safesort.classifier."""

from __future__ import annotations

from safesort.classifier import OTHER_CATEGORY, classify
from safesort.config import DEFAULT_EXTENSIONS


def test_classify_documents() -> None:
    assert classify(".pdf", DEFAULT_EXTENSIONS) == "documents"
    assert classify(".docx", DEFAULT_EXTENSIONS) == "documents"
    assert classify(".txt", DEFAULT_EXTENSIONS) == "documents"
    assert classify(".odt", DEFAULT_EXTENSIONS) == "documents"


def test_classify_images() -> None:
    assert classify(".jpg", DEFAULT_EXTENSIONS) == "images"
    assert classify(".jpeg", DEFAULT_EXTENSIONS) == "images"
    assert classify(".png", DEFAULT_EXTENSIONS) == "images"
    assert classify(".webp", DEFAULT_EXTENSIONS) == "images"


def test_classify_video() -> None:
    assert classify(".mp4", DEFAULT_EXTENSIONS) == "video"
    assert classify(".mkv", DEFAULT_EXTENSIONS) == "video"
    assert classify(".mov", DEFAULT_EXTENSIONS) == "video"


def test_classify_audio() -> None:
    assert classify(".mp3", DEFAULT_EXTENSIONS) == "audio"
    assert classify(".wav", DEFAULT_EXTENSIONS) == "audio"
    assert classify(".flac", DEFAULT_EXTENSIONS) == "audio"


def test_classify_archives() -> None:
    assert classify(".zip", DEFAULT_EXTENSIONS) == "archives"
    assert classify(".tar", DEFAULT_EXTENSIONS) == "archives"
    assert classify(".gz", DEFAULT_EXTENSIONS) == "archives"
    assert classify(".7z", DEFAULT_EXTENSIONS) == "archives"


def test_classify_code() -> None:
    assert classify(".py", DEFAULT_EXTENSIONS) == "code"
    assert classify(".js", DEFAULT_EXTENSIONS) == "code"
    assert classify(".ts", DEFAULT_EXTENSIONS) == "code"
    assert classify(".rs", DEFAULT_EXTENSIONS) == "code"
    assert classify(".java", DEFAULT_EXTENSIONS) == "code"


def test_classify_data() -> None:
    assert classify(".json", DEFAULT_EXTENSIONS) == "data"
    assert classify(".csv", DEFAULT_EXTENSIONS) == "data"
    assert classify(".xml", DEFAULT_EXTENSIONS) == "data"


def test_classify_fallback_other() -> None:
    assert classify(".exe", DEFAULT_EXTENSIONS) == OTHER_CATEGORY
    assert classify("", DEFAULT_EXTENSIONS) == OTHER_CATEGORY
    assert classify(".unknownext", DEFAULT_EXTENSIONS) == OTHER_CATEGORY


def test_classify_is_case_insensitive() -> None:
    assert classify(".PDF", DEFAULT_EXTENSIONS) == "documents"
    assert classify(".Jpg", DEFAULT_EXTENSIONS) == "images"


def test_classify_with_custom_mapping() -> None:
    mapping = {"custom": [".foo", ".bar"]}
    assert classify(".foo", mapping) == "custom"
    assert classify(".baz", mapping) == OTHER_CATEGORY
