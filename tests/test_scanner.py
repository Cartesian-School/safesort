"""Tests for safesort.scanner."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from safesort.config import Config
from safesort.scanner import scan


def test_scan_empty_directory_returns_nothing(tmp_path: Path) -> None:
    assert scan(tmp_path, Config()) == []


def test_scan_finds_nested_files_at_multiple_depths(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("top level")
    nested = tmp_path / "sub1" / "sub2"
    nested.mkdir(parents=True)
    (nested / "b.txt").write_text("deeply nested")
    (tmp_path / "sub1" / "c.txt").write_text("one level down")

    results = scan(tmp_path, Config())
    names = {f.path.name for f in results}
    assert names == {"a.txt", "b.txt", "c.txt"}
    assert len(results) == 3


def test_scan_reports_correct_size_and_extension(tmp_path: Path) -> None:
    file_path = tmp_path / "photo.JPG"
    file_path.write_bytes(b"x" * 123)

    [info] = scan(tmp_path, Config())
    assert info.path == file_path
    assert info.size == 123
    assert info.extension == ".jpg"  # lower-cased


def test_scan_skips_custom_excluded_directories(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_text("keep me")
    excluded_dir = tmp_path / "node_modules"
    excluded_dir.mkdir()
    (excluded_dir / "skip.txt").write_text("skip me")

    config = Config(exclude=(".git", ".venv", "node_modules"))
    results = scan(tmp_path, config)
    names = {f.path.name for f in results}
    assert names == {"keep.txt"}


def test_scan_never_reprocesses_the_destination_directory(tmp_path: Path) -> None:
    (tmp_path / "input.txt").write_text("input")
    sorted_dir = tmp_path / "Sorted" / "documents"
    sorted_dir.mkdir(parents=True)
    (sorted_dir / "already_sorted.txt").write_text("already sorted")

    config = Config()  # default destination is "Sorted"
    results = scan(tmp_path, config)
    names = {f.path.name for f in results}
    assert names == {"input.txt"}
    assert "already_sorted.txt" not in names


def test_scan_skips_symlinked_file(tmp_path: Path) -> None:
    real_file = tmp_path / "real.txt"
    real_file.write_text("real content")
    symlink = tmp_path / "link.txt"
    symlink.symlink_to(real_file)

    results = scan(tmp_path, Config())
    names = {f.path.name for f in results}
    assert names == {"real.txt"}


def test_scan_skips_symlinked_directory(tmp_path: Path) -> None:
    real_dir = tmp_path / "real_dir"
    real_dir.mkdir()
    (real_dir / "inside.txt").write_text("inside content")

    link_dir = tmp_path / "link_dir"
    link_dir.symlink_to(real_dir, target_is_directory=True)

    results = scan(tmp_path, Config())
    # Only the file reached via the real directory should show up; the
    # symlinked directory must never be followed.
    assert len(results) == 1
    assert results[0].path == real_dir / "inside.txt"


@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="permission bits are not enforced for root or on non-POSIX platforms",
)
def test_scan_skips_unreadable_directory_without_crashing(tmp_path: Path) -> None:
    (tmp_path / "visible.txt").write_text("visible")
    locked_dir = tmp_path / "locked"
    locked_dir.mkdir()
    (locked_dir / "hidden.txt").write_text("hidden")

    original_mode = locked_dir.stat().st_mode
    locked_dir.chmod(0o000)
    try:
        results = scan(tmp_path, Config())
    finally:
        locked_dir.chmod(original_mode)

    names = {f.path.name for f in results}
    assert names == {"visible.txt"}
