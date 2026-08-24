"""Tests for safesort.manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from safesort.config import Config
from safesort.executor import apply_plan
from safesort.manifest import (
    ManifestError,
    find_latest_manifest,
    history_dir,
    read_manifest,
    undo,
    write_manifest,
)
from safesort.models import CompletedMove, FileInfo, OperationManifest
from safesort.planner import build_plan


def _file(path: Path, size: int = 10) -> FileInfo:
    return FileInfo(path=path, size=size, extension=path.suffix.lower())


def test_find_latest_manifest_with_no_history_returns_none(tmp_path: Path) -> None:
    assert find_latest_manifest(tmp_path) is None


def test_write_and_read_manifest_round_trip(tmp_path: Path) -> None:
    moves = [
        CompletedMove(
            source=tmp_path / "a.txt",
            destination=tmp_path / "Sorted" / "documents" / "a.txt",
            completed=True,
        ),
        CompletedMove(
            source=tmp_path / "b.txt",
            destination=tmp_path / "Sorted" / "documents" / "b.txt",
            completed=False,
            error="boom",
        ),
    ]

    manifest, path = write_manifest(tmp_path, moves)

    assert path.exists()
    assert path.parent == history_dir(tmp_path)

    read_back = read_manifest(path)
    assert read_back.operation_id == manifest.operation_id
    assert read_back.root == tmp_path
    assert read_back.moves == tuple(moves)


def test_find_latest_manifest_returns_the_most_recent(tmp_path: Path) -> None:
    _manifest1, path1 = write_manifest(tmp_path, [])
    # Force a distinguishable, later operation id.
    later_dir = history_dir(tmp_path)
    later_path = later_dir / "99999999T999999999999.json"
    later_path.write_text(path1.read_text(), encoding="utf-8")

    latest = find_latest_manifest(tmp_path)
    assert latest == later_path


def test_read_manifest_missing_file_raises_manifest_error(tmp_path: Path) -> None:
    with pytest.raises(ManifestError):
        read_manifest(tmp_path / "does_not_exist.json")


def test_read_manifest_with_invalid_json_raises_manifest_error(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ManifestError):
        read_manifest(bad_file)


def test_read_manifest_with_missing_fields_raises_manifest_error(tmp_path: Path) -> None:
    bad_file = tmp_path / "incomplete.json"
    bad_file.write_text(json.dumps({"operation_id": "123"}), encoding="utf-8")
    with pytest.raises(ManifestError):
        read_manifest(bad_file)


def test_read_manifest_with_wrong_types_raises_manifest_error(tmp_path: Path) -> None:
    bad_file = tmp_path / "wrong_types.json"
    bad_file.write_text(
        json.dumps({"operation_id": "123", "root": "/x", "timestamp": "now", "moves": "not-a-list"}),
        encoding="utf-8",
    )
    with pytest.raises(ManifestError):
        read_manifest(bad_file)


def test_undo_restores_files_to_original_location(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("hello")
    plan = build_plan([_file(source)], tmp_path, Config())
    results = apply_plan(plan)
    manifest, _path = write_manifest(tmp_path, results)

    destination = plan.operations[0].destination
    assert destination.exists()
    assert not source.exists()

    result = undo(manifest)

    assert len(result.restored) == 1
    assert not result.conflicts
    assert source.exists()
    assert source.read_text() == "hello"
    assert not destination.exists()


def test_undo_skips_moves_that_were_never_completed(tmp_path: Path) -> None:
    manifest = OperationManifest(
        operation_id="20260101T000000000000",
        root=tmp_path,
        timestamp="2026-01-01T00:00:00",
        moves=(
            CompletedMove(
                source=tmp_path / "never_moved.txt",
                destination=tmp_path / "Sorted" / "other" / "never_moved.txt",
                completed=False,
                error="did not happen",
            ),
        ),
    )

    result = undo(manifest)

    assert result.restored == ()
    assert result.conflicts == ()


def test_undo_refuses_to_overwrite_and_still_restores_other_entries(tmp_path: Path) -> None:
    conflict_source = tmp_path / "conflict.txt"
    clean_source = tmp_path / "clean.txt"
    conflict_source.write_text("original conflict content")
    clean_source.write_text("original clean content")

    config = Config()
    plan = build_plan([_file(conflict_source), _file(clean_source)], tmp_path, config)
    results = apply_plan(plan)
    manifest, _path = write_manifest(tmp_path, results)

    # Something new now occupies the original location of one source file.
    conflict_source.write_text("a brand new, unrelated file")

    result = undo(manifest)

    assert len(result.conflicts) == 1
    assert result.conflicts[0].source == conflict_source
    assert conflict_source.read_text() == "a brand new, unrelated file"  # untouched

    assert len(result.restored) == 1
    assert clean_source.exists()
    assert clean_source.read_text() == "original clean content"
