"""Command-line interface for SafeSort.

Five subcommands: ``scan``, ``plan``, ``apply``, ``duplicates``, ``undo``.
``scan``, ``plan``, and ``duplicates`` are strictly read-only. ``apply`` is
the only command that ever moves a file, and it does so as soon as it's
invoked — the explicit subcommand *is* the confirmation, there is no
additional interactive prompt.

Output printed to stdout here is the concise, user-facing summary shown in
the README. Anything diagnostic (warnings about skipped files, permission
errors while scanning, etc.) goes through the :mod:`logging` module
instead, kept deliberately separate from that summary output.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path

from safesort.classifier import classify
from safesort.config import Config, ConfigError, load_config
from safesort.duplicates import find_duplicates
from safesort.executor import apply_plan
from safesort.manifest import ManifestError, find_latest_manifest, read_manifest, undo, write_manifest
from safesort.planner import build_plan
from safesort.scanner import scan

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with all five subcommands."""
    parser = argparse.ArgumentParser(
        prog="safesort",
        description=(
            "SafeSort: a safe, non-destructive file organizer. "
            "scan/plan/duplicates never modify anything; only 'apply' moves files."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser(
        "scan", help="List files found under ROOT, grouped by category (read-only)."
    )
    scan_parser.add_argument("root", type=Path, help="Directory to scan.")

    plan_parser = subparsers.add_parser(
        "plan",
        help="Show the moves that would be made under ROOT, without changing anything (read-only).",
    )
    plan_parser.add_argument("root", type=Path, help="Directory to plan for.")

    apply_parser = subparsers.add_parser(
        "apply",
        help="Move files under ROOT into Sorted/<category>/ and record an undo manifest.",
    )
    apply_parser.add_argument("root", type=Path, help="Directory to organize.")

    duplicates_parser = subparsers.add_parser(
        "duplicates",
        help="Report groups of files with identical content under ROOT (read-only, never deletes).",
    )
    duplicates_parser.add_argument("root", type=Path, help="Directory to scan for duplicates.")

    undo_parser = subparsers.add_parser(
        "undo", help="Undo the most recent 'apply' run recorded under ROOT."
    )
    undo_parser.add_argument(
        "root",
        type=Path,
        nargs="?",
        default=Path("."),
        help="Directory whose most recent apply should be undone (default: current directory).",
    )

    return parser


def _require_directory(root: Path) -> int | None:
    """Print an error and return an exit code if ``root`` isn't usable, else None."""
    if not root.exists():
        print(f"Error: path does not exist: {root}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"Error: not a directory: {root}", file=sys.stderr)
        return 1
    return None


def _load_config(root: Path) -> tuple[Config | None, int | None]:
    try:
        return load_config(root), None
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return None, 1


def cmd_scan(args: argparse.Namespace) -> int:
    root: Path = args.root
    if (code := _require_directory(root)) is not None:
        return code
    config, code = _load_config(root)
    if config is None:
        return code if code is not None else 1

    files = scan(root, config)
    counts: dict[str, int] = defaultdict(int)
    for file_info in files:
        counts[classify(file_info.extension, config.extensions)] += 1

    print(f"Files scanned: {len(files)}")
    category_order = [*config.extensions.keys(), "other"]
    for category in category_order:
        if counts.get(category):
            print(f"{category.capitalize()}: {counts[category]}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    root: Path = args.root
    if (code := _require_directory(root)) is not None:
        return code
    config, code = _load_config(root)
    if config is None:
        return code if code is not None else 1

    files = scan(root, config)
    plan = build_plan(files, root, config)
    print(f"{len(plan.operations)} move operations planned.")
    print("No files have been changed.")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    root: Path = args.root
    if (code := _require_directory(root)) is not None:
        return code
    config, code = _load_config(root)
    if config is None:
        return code if code is not None else 1

    files = scan(root, config)
    plan = build_plan(files, root, config)
    results = apply_plan(plan)
    _manifest, manifest_file = write_manifest(root, results)

    succeeded = [move for move in results if move.completed]
    failed = [move for move in results if not move.completed]

    print(f"Applied {len(succeeded)} moves.")
    if failed:
        print(f"{len(failed)} moves failed:")
        for move in failed:
            print(f"  {move.source} -> {move.destination}: {move.error}")
    print("Manifest written to:")
    print(manifest_file)

    return 1 if failed else 0


def cmd_duplicates(args: argparse.Namespace) -> int:
    root: Path = args.root
    if (code := _require_directory(root)) is not None:
        return code
    config, code = _load_config(root)
    if config is None:
        return code if code is not None else 1

    files = scan(root, config)
    groups = find_duplicates(files)

    if not groups:
        print("No duplicate files found.")
        return 0

    print(f"Found {len(groups)} duplicate group(s):")
    for index, group in enumerate(groups, start=1):
        print(f"Group {index}: {len(group.files)} files, {group.size} bytes each, sha256={group.digest}")
        for file_info in group.files:
            print(f"  {file_info.path}")
    return 0


def cmd_undo(args: argparse.Namespace) -> int:
    root: Path = args.root
    if (code := _require_directory(root)) is not None:
        return code

    manifest_file = find_latest_manifest(root)
    if manifest_file is None:
        print(f"No SafeSort history found under {root}.")
        return 1

    try:
        manifest = read_manifest(manifest_file)
    except ManifestError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    result = undo(manifest)
    print(f"Restored {len(result.restored)} moves.")
    if result.conflicts:
        print(f"{len(result.conflicts)} moves could not be restored:")
        for conflict in result.conflicts:
            print(f"  {conflict.destination} -> {conflict.source}: {conflict.reason}")

    return 1 if result.conflicts else 0


_HANDLERS = {
    "scan": cmd_scan,
    "plan": cmd_plan,
    "apply": cmd_apply,
    "duplicates": cmd_duplicates,
    "undo": cmd_undo,
}


def main(argv: list[str] | None = None) -> int:
    """Entry point used by both the console script and ``python -m safesort``."""
    _configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = _HANDLERS[args.command]

    try:
        return handler(args)
    except PermissionError as exc:
        print(f"Error: permission denied: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"Error: file not found: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
