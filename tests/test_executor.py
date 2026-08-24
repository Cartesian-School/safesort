"""Tests for safesort.executor."""

from __future__ import annotations

from pathlib import Path

from safesort.config import Config
from safesort.executor import apply_plan
from safesort.models import FileInfo, MoveOperation, SortPlan
from safesort.planner import build_plan
from safesort.scanner import scan


def _file(path: Path, size: int = 10) -> FileInfo:
    return FileInfo(path=path, size=size, extension=path.suffix.lower())


def test_apply_plan_moves_files_and_creates_directories(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("hello")
    files = [_file(source)]
    plan = build_plan(files, tmp_path, Config())

    results = apply_plan(plan)

    assert len(results) == 1
    assert results[0].completed is True
    destination = plan.operations[0].destination
    assert destination.exists()
    assert destination.read_text() == "hello"
    assert not source.exists()


def test_apply_plan_handles_full_lifecycle_via_scan_and_plan(tmp_path: Path) -> None:
    (tmp_path / "photo.png").write_bytes(b"fake image bytes")
    (tmp_path / "song.mp3").write_bytes(b"fake audio bytes")

    config = Config()
    files = scan(tmp_path, config)
    plan = build_plan(files, tmp_path, config)
    results = apply_plan(plan)

    assert all(move.completed for move in results)
    assert (tmp_path / "Sorted" / "images" / "photo.png").exists()
    assert (tmp_path / "Sorted" / "audio" / "song.mp3").exists()


def test_apply_plan_records_failure_when_source_vanishes_before_apply(tmp_path: Path) -> None:
    source = tmp_path / "ghost.txt"
    source.write_text("will vanish")
    files = [_file(source)]
    plan = build_plan(files, tmp_path, Config())

    # Simulate the file disappearing after planning but before applying.
    source.unlink()

    results = apply_plan(plan)

    assert len(results) == 1
    assert results[0].completed is False
    assert results[0].error is not None


def test_apply_plan_continues_after_one_failure(tmp_path: Path) -> None:
    good_source = tmp_path / "good.txt"
    good_source.write_text("fine")
    missing_source = tmp_path / "missing.txt"
    # Note: missing_source is never created on disk.

    plan = SortPlan(
        root=tmp_path,
        operations=(
            MoveOperation(source=missing_source, destination=tmp_path / "Sorted" / "other" / "missing.txt"),
            MoveOperation(source=good_source, destination=tmp_path / "Sorted" / "documents" / "good.txt"),
        ),
    )

    results = apply_plan(plan)

    assert len(results) == 2
    assert results[0].completed is False
    assert results[1].completed is True
    assert (tmp_path / "Sorted" / "documents" / "good.txt").exists()


def test_apply_plan_never_overwrites_a_destination_that_appeared_after_planning(
    tmp_path: Path,
) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("new content")
    destination = tmp_path / "Sorted" / "documents" / "notes.txt"

    plan = SortPlan(root=tmp_path, operations=(MoveOperation(source=source, destination=destination),))

    # Simulate a race: something else creates the destination after the
    # plan was built but before apply runs.
    destination.parent.mkdir(parents=True)
    destination.write_text("surprise existing content")

    results = apply_plan(plan)

    assert results[0].completed is False
    assert destination.read_text() == "surprise existing content"  # never overwritten
    assert source.exists()  # source left in place since the move was refused
