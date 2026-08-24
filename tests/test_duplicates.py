"""Tests for safesort.duplicates."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import safesort.duplicates as duplicates_module
from safesort.duplicates import files_equal, find_duplicates, sha256_file
from safesort.models import FileInfo


def _file(path: Path) -> FileInfo:
    return FileInfo(path=path, size=path.stat().st_size, extension=path.suffix.lower())


def test_two_empty_files_are_detected_as_duplicates(tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_bytes(b"")
    b.write_bytes(b"")

    groups = find_duplicates([_file(a), _file(b)])

    assert len(groups) == 1
    assert groups[0].size == 0
    assert {f.path for f in groups[0].files} == {a, b}


def test_real_duplicate_content_files_are_grouped(tmp_path: Path) -> None:
    content = b"identical bytes across two files\n" * 100
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(content)
    b.write_bytes(content)

    groups = find_duplicates([_file(a), _file(b)])

    assert len(groups) == 1
    assert groups[0].digest == hashlib.sha256(content).hexdigest()
    assert len(groups[0].files) == 2


def test_files_with_same_size_but_different_content_are_not_grouped(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"AAAAAAAAAA")
    b.write_bytes(b"BBBBBBBBBB")

    groups = find_duplicates([_file(a), _file(b)])

    assert groups == []


def test_files_with_different_sizes_are_never_hashed_or_grouped(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"short")
    b.write_bytes(b"a much longer piece of content")

    groups = find_duplicates([_file(a), _file(b)])

    assert groups == []


def test_unique_file_is_not_included_in_any_group(tmp_path: Path) -> None:
    content = b"shared content"
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    unique = tmp_path / "unique.bin"
    a.write_bytes(content)
    b.write_bytes(content)
    unique.write_bytes(b"totally different and unique content, longer too")

    groups = find_duplicates([_file(a), _file(b), _file(unique)])

    assert len(groups) == 1
    paths_in_groups = {f.path for f in groups[0].files}
    assert unique not in paths_in_groups


def test_sha256_file_matches_direct_hash_for_small_file(tmp_path: Path) -> None:
    path = tmp_path / "small.bin"
    data = b"a small amount of data"
    path.write_bytes(data)

    assert sha256_file(path) == hashlib.sha256(data).hexdigest()


def test_sha256_file_matches_direct_hash_for_multi_chunk_file(tmp_path: Path) -> None:
    # A few MB, using a small chunk size, so the incremental read loop in
    # sha256_file has to run through several iterations to prove chunked
    # reading produces the same digest as hashing all the bytes at once.
    path = tmp_path / "large.bin"
    data = os.urandom(3 * 1024 * 1024 + 12345)  # not an exact multiple of the chunk size
    path.write_bytes(data)

    expected = hashlib.sha256(data).hexdigest()
    actual = sha256_file(path, chunk_size=1024 * 1024)

    assert actual == expected


def test_find_duplicates_with_no_files_returns_empty() -> None:
    assert find_duplicates([]) == []


def test_files_equal_true_for_identical_multi_chunk_content(tmp_path: Path) -> None:
    data = os.urandom(3 * 1024 * 1024 + 7)
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(data)
    b.write_bytes(data)

    assert files_equal(a, b, chunk_size=1024 * 1024) is True


def test_files_equal_false_when_bytes_differ_after_first_chunk(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"x" * (2 * 1024 * 1024))
    b.write_bytes(b"x" * (2 * 1024 * 1024 - 1) + b"y")

    assert files_equal(a, b, chunk_size=1024 * 1024) is False


def test_find_duplicates_excludes_a_hash_collision_confirmed_different_by_bytes(
    tmp_path: Path, monkeypatch
) -> None:
    """A matching SHA-256 digest is a fast filter, not proof — force two
    different-content, same-size files to hash identically (simulating a
    collision) and confirm find_duplicates() still refuses to group them
    once the byte-by-byte confirmation step sees they actually differ."""
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"AAAAAAAAAA")
    b.write_bytes(b"BBBBBBBBBB")

    monkeypatch.setattr(duplicates_module, "sha256_file", lambda path, chunk_size=None: "forced-collision")

    groups = find_duplicates([_file(a), _file(b)])

    assert groups == []
