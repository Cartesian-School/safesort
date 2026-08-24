"""Tests for safesort.planner."""

from __future__ import annotations

from pathlib import Path

from safesort.config import Config
from safesort.models import FileInfo
from safesort.planner import build_plan


def _file(path: Path, size: int = 10) -> FileInfo:
    return FileInfo(path=path, size=size, extension=path.suffix.lower())


def test_build_plan_is_pure_and_touches_nothing(tmp_path: Path) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text("hello")
    files = [_file(file_path)]

    plan = build_plan(files, tmp_path, Config())

    assert not (tmp_path / "Sorted").exists()
    assert file_path.exists()  # untouched
    assert len(plan.operations) == 1


def test_build_plan_routes_by_category(tmp_path: Path) -> None:
    doc = tmp_path / "report.pdf"
    img = tmp_path / "photo.jpg"
    other = tmp_path / "mystery.xyz"
    for p in (doc, img, other):
        p.write_text("data")

    plan = build_plan([_file(doc), _file(img), _file(other)], tmp_path, Config())
    destinations = {op.source.name: op.destination for op in plan.operations}

    assert destinations["report.pdf"] == tmp_path / "Sorted" / "documents" / "report.pdf"
    assert destinations["photo.jpg"] == tmp_path / "Sorted" / "images" / "photo.jpg"
    assert destinations["mystery.xyz"] == tmp_path / "Sorted" / "other" / "mystery.xyz"


def test_build_plan_avoids_collision_with_existing_file_on_disk(tmp_path: Path) -> None:
    source = tmp_path / "a" / "notes.txt"
    source.parent.mkdir()
    source.write_text("new content")

    existing_dest_dir = tmp_path / "Sorted" / "documents"
    existing_dest_dir.mkdir(parents=True)
    (existing_dest_dir / "notes.txt").write_text("already there")

    plan = build_plan([_file(source)], tmp_path, Config())

    [operation] = plan.operations
    assert operation.destination == existing_dest_dir / "notes (1).txt"
    # The pre-existing file must not have been touched.
    assert (existing_dest_dir / "notes.txt").read_text() == "already there"


def test_build_plan_avoids_collision_between_two_queued_operations(tmp_path: Path) -> None:
    first = tmp_path / "dir1" / "notes.txt"
    second = tmp_path / "dir2" / "notes.txt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("first")
    second.write_text("second")

    plan = build_plan([_file(first), _file(second)], tmp_path, Config())

    destinations = {op.destination for op in plan.operations}
    assert len(destinations) == 2  # never collide
    names = sorted(d.name for d in destinations)
    assert names == ["notes (1).txt", "notes.txt"]


def test_build_plan_generates_multiple_safe_alternatives(tmp_path: Path) -> None:
    dest_dir = tmp_path / "Sorted" / "documents"
    dest_dir.mkdir(parents=True)
    (dest_dir / "notes.txt").write_text("existing 0")
    (dest_dir / "notes (1).txt").write_text("existing 1")

    source = tmp_path / "notes.txt"
    source.write_text("new")

    plan = build_plan([_file(source)], tmp_path, Config())

    [operation] = plan.operations
    assert operation.destination == dest_dir / "notes (2).txt"


def test_build_plan_with_custom_destination(tmp_path: Path) -> None:
    source = tmp_path / "archive.zip"
    source.write_text("zip data")
    config = Config(destination="Organized")

    plan = build_plan([_file(source)], tmp_path, config)

    [operation] = plan.operations
    assert operation.destination == tmp_path / "Organized" / "archives" / "archive.zip"
