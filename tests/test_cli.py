"""Tests for safesort.cli."""

from __future__ import annotations

from pathlib import Path

import pytest

from safesort.cli import build_parser, main


def test_help_exits_zero_and_lists_all_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0

    output = capsys.readouterr().out
    for subcommand in ("scan", "plan", "apply", "duplicates", "undo"):
        assert subcommand in output


def test_no_subcommand_is_a_controlled_failure(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code != 0


def test_invalid_subcommand_is_a_controlled_failure() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["not-a-real-command"])
    assert excinfo.value.code != 0


@pytest.mark.parametrize("subcommand", ["scan", "plan", "apply", "duplicates"])
def test_each_subcommand_requires_a_root_argument(subcommand: str) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([subcommand])
    assert excinfo.value.code != 0


def test_undo_root_argument_is_optional() -> None:
    parser = build_parser()
    args = parser.parse_args(["undo"])
    assert args.root == Path(".")


@pytest.mark.parametrize("subcommand", ["scan", "plan", "apply", "duplicates", "undo"])
def test_subcommand_help_works(subcommand: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([subcommand, "--help"])
    assert excinfo.value.code == 0
    assert subcommand in capsys.readouterr().out


def test_parser_parses_each_subcommand_with_root() -> None:
    parser = build_parser()
    for subcommand in ("scan", "plan", "apply", "duplicates"):
        args = parser.parse_args([subcommand, "/tmp/example"])
        assert args.command == subcommand
        assert args.root == Path("/tmp/example")


def test_scan_on_nonexistent_path_returns_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "does_not_exist"
    code = main(["scan", str(missing)])
    assert code != 0
    assert "does not exist" in capsys.readouterr().err


def test_scan_on_a_file_instead_of_a_directory_returns_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_file = tmp_path / "not_a_dir.txt"
    a_file.write_text("hi")
    code = main(["scan", str(a_file)])
    assert code != 0
    assert "not a directory" in capsys.readouterr().err


def test_scan_reports_counts_by_category(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "a.pdf").write_text("doc")
    (tmp_path / "b.jpg").write_bytes(b"img")
    (tmp_path / "c.mystery").write_text("other")

    code = main(["scan", str(tmp_path)])
    out = capsys.readouterr().out

    assert code == 0
    assert "Files scanned: 3" in out
    assert "Documents: 1" in out
    assert "Images: 1" in out
    assert "Other: 1" in out


def test_plan_reports_operation_count_and_makes_no_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "a.pdf").write_text("doc")
    (tmp_path / "b.jpg").write_bytes(b"img")

    code = main(["plan", str(tmp_path)])
    out = capsys.readouterr().out

    assert code == 0
    assert "2 move operations planned." in out
    assert "No files have been changed." in out
    assert not (tmp_path / "Sorted").exists()


def test_full_lifecycle_scan_plan_apply_duplicates_undo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "report.pdf").write_text("a document")
    (tmp_path / "photo.jpg").write_bytes(b"an image")
    duplicate_content = b"same bytes in both files"
    (tmp_path / "copy1.txt").write_bytes(duplicate_content)
    (tmp_path / "copy2.txt").write_bytes(duplicate_content)

    assert main(["scan", str(tmp_path)]) == 0
    capsys.readouterr()

    assert main(["plan", str(tmp_path)]) == 0
    capsys.readouterr()

    assert main(["duplicates", str(tmp_path)]) == 0
    dup_out = capsys.readouterr().out
    assert "Found 1 duplicate group(s):" in dup_out

    assert main(["apply", str(tmp_path)]) == 0
    apply_out = capsys.readouterr().out
    assert "Applied 4 moves." in apply_out
    assert "Manifest written to:" in apply_out

    assert (tmp_path / "Sorted" / "documents" / "report.pdf").exists()
    assert (tmp_path / "Sorted" / "images" / "photo.jpg").exists()
    assert not (tmp_path / "report.pdf").exists()

    # Re-running scan/apply must never re-process the Sorted output.
    assert main(["scan", str(tmp_path)]) == 0
    rescan_out = capsys.readouterr().out
    assert "Files scanned: 0" in rescan_out

    assert main(["undo", str(tmp_path)]) == 0
    undo_out = capsys.readouterr().out
    assert "Restored 4 moves." in undo_out

    assert (tmp_path / "report.pdf").exists()
    assert (tmp_path / "photo.jpg").exists()
    assert (tmp_path / "copy1.txt").exists()
    assert (tmp_path / "copy2.txt").exists()


def test_undo_with_no_history_reports_and_returns_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["undo", str(tmp_path)])
    assert code != 0
    assert "No SafeSort history found" in capsys.readouterr().out


def test_duplicates_with_no_duplicates_reports_none(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "unique.txt").write_text("only one of these")
    code = main(["duplicates", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "No duplicate files found." in out
