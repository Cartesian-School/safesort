"""Frozen data structures shared across SafeSort's modules.

Everything here is intentionally immutable (``frozen=True``). SafeSort's
safety story depends on a clean separation between *planning* (pure, no
filesystem writes) and *execution* (the only step allowed to touch disk),
and frozen dataclasses make it impossible for a planning function to
accidentally mutate a plan that a caller is still holding a reference to.

``Path`` objects are used everywhere in memory because they are the natural
type for filesystem locations. The manifest system is the one place that
needs to leave memory (it is written to JSON on disk), so the conversion to
and from plain strings happens explicitly in :mod:`safesort.manifest`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileInfo:
    """A single regular file discovered by the scanner.

    Attributes:
        path: Absolute (or caller-relative) path to the file.
        size: Size in bytes, as reported by ``stat()``.
        extension: Lower-cased extension including the leading dot
            (e.g. ``".jpg"``), or ``""`` if the file has no extension.
    """

    path: Path
    size: int
    extension: str


@dataclass(frozen=True)
class MoveOperation:
    """A single planned (not yet performed) file move."""

    source: Path
    destination: Path


@dataclass(frozen=True)
class SortPlan:
    """A complete, non-destructive plan of moves for one root directory."""

    root: Path
    operations: tuple[MoveOperation, ...]


@dataclass(frozen=True)
class DuplicateGroup:
    """A group of two or more files whose content is byte-for-byte identical.

    Attributes:
        size: The shared file size in bytes.
        digest: The shared SHA-256 hex digest.
        files: The files that make up this group (always length >= 2).
    """

    size: int
    digest: str
    files: tuple[FileInfo, ...]


@dataclass(frozen=True)
class CompletedMove:
    """The recorded outcome of attempting a single planned move.

    ``completed`` is ``False`` when the move was attempted but failed (for
    example because the source file vanished between planning and applying,
    or a permission error occurred). Failed moves are still recorded so the
    manifest is a complete, honest account of what happened.
    """

    source: Path
    destination: Path
    completed: bool
    error: str | None = None


@dataclass(frozen=True)
class OperationManifest:
    """A record of one completed (or partially completed) ``apply`` run.

    This is what gets serialized to JSON under
    ``<root>/.safesort/history/<operation_id>.json`` and read back by
    ``undo``.
    """

    operation_id: str
    root: Path
    timestamp: str
    moves: tuple[CompletedMove, ...]


@dataclass(frozen=True)
class UndoConflict:
    """A single move that ``undo`` refused to restore, and why."""

    source: Path
    destination: Path
    reason: str


@dataclass(frozen=True)
class UndoResult:
    """The outcome of an ``undo`` run: what was restored, and what wasn't."""

    restored: tuple[CompletedMove, ...]
    conflicts: tuple[UndoConflict, ...]
