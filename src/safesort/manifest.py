"""Recording completed ``apply`` runs, and undoing the most recent one.

Every completed ``apply`` writes a JSON manifest to
``<root>/.safesort/history/<operation_id>.json``. That manifest is the only
thing ``undo`` has to go on, so writing it, reading it back, and undoing
from it are kept together in this one module.

Manifests are the one place SafeSort's in-memory :class:`Path`-based models
have to cross into JSON, which has no ``Path`` type — paths are stored as
plain strings and converted back to :class:`~pathlib.Path` on read.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from safesort.config import STATE_DIRNAME
from safesort.models import CompletedMove, OperationManifest, UndoConflict, UndoResult

logger = logging.getLogger(__name__)

#: Subdirectory of the state directory that operation manifests live under.
HISTORY_SUBDIR = "history"


class ManifestError(Exception):
    """Raised when a manifest file cannot be read as a valid manifest."""


def history_dir(root: Path) -> Path:
    """Return the directory that operation manifests for ``root`` live in."""
    return Path(root) / STATE_DIRNAME / HISTORY_SUBDIR


def new_operation_id() -> str:
    """Generate a new, lexicographically time-sortable operation id."""
    return datetime.now().strftime("%Y%m%dT%H%M%S%f")


def manifest_path(root: Path, operation_id: str) -> Path:
    """Return the path a manifest with ``operation_id`` would be written to."""
    return history_dir(root) / f"{operation_id}.json"


def write_manifest(root: Path, moves: list[CompletedMove]) -> tuple[OperationManifest, Path]:
    """Write a new manifest recording the outcome of an ``apply`` run.

    Returns the in-memory :class:`OperationManifest` together with the path
    it was written to (the CLI reports that path to the user).
    """
    operation_id = new_operation_id()
    manifest = OperationManifest(
        operation_id=operation_id,
        root=Path(root),
        timestamp=datetime.now().isoformat(timespec="seconds"),
        moves=tuple(moves),
    )
    path = manifest_path(root, operation_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "operation_id": manifest.operation_id,
        "root": str(manifest.root),
        "timestamp": manifest.timestamp,
        "moves": [
            {
                "source": str(move.source),
                "destination": str(move.destination),
                "completed": move.completed,
                "error": move.error,
            }
            for move in manifest.moves
        ],
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")

    logger.info("Wrote manifest %s", path)
    return manifest, path


def find_latest_manifest(root: Path) -> Path | None:
    """Return the most recently written manifest under ``root``, if any.

    Operation ids are timestamps formatted so that lexicographic order
    matches chronological order, so the latest manifest is simply the last
    one in sorted filename order.
    """
    directory = history_dir(root)
    if not directory.is_dir():
        return None
    candidates = sorted(directory.glob("*.json"))
    if not candidates:
        return None
    return candidates[-1]


def read_manifest(path: Path) -> OperationManifest:
    """Read and validate a manifest file, raising :class:`ManifestError` on failure.

    A missing file, invalid JSON, or JSON that doesn't have the shape of a
    manifest all raise a clear :class:`ManifestError` rather than an
    unhelpful raw traceback or, worse, being silently treated as valid.
    """
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise ManifestError(f"Manifest file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Manifest file {path} is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise ManifestError(f"Could not read manifest file {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError(f"Manifest file {path} does not contain a JSON object")

    try:
        operation_id = data["operation_id"]
        root = data["root"]
        timestamp = data["timestamp"]
        moves_raw = data["moves"]
        if not isinstance(operation_id, str) or not isinstance(root, str):
            raise TypeError("'operation_id' and 'root' must be strings")
        if not isinstance(timestamp, str):
            raise TypeError("'timestamp' must be a string")
        if not isinstance(moves_raw, list):
            raise TypeError("'moves' must be a list")

        moves = []
        for entry in moves_raw:
            if not isinstance(entry, dict):
                raise TypeError("each entry in 'moves' must be an object")
            moves.append(
                CompletedMove(
                    source=Path(entry["source"]),
                    destination=Path(entry["destination"]),
                    completed=bool(entry["completed"]),
                    error=entry.get("error"),
                )
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise ManifestError(f"Manifest file {path} has an invalid or missing field: {exc}") from exc

    return OperationManifest(
        operation_id=operation_id,
        root=Path(root),
        timestamp=timestamp,
        moves=tuple(moves),
    )


def undo(manifest: OperationManifest) -> UndoResult:
    """Reverse every completed move in ``manifest``, refusing to overwrite.

    Only moves recorded with ``completed=True`` are considered — moves that
    failed during ``apply`` never touched the filesystem, so there is
    nothing to undo for them. For each completed move, if something now
    exists at the original source path, that specific restoration is
    refused (reported as a conflict) rather than overwritten; every other
    non-conflicting move in the manifest is still restored.
    """
    restored: list[CompletedMove] = []
    conflicts: list[UndoConflict] = []

    for move in manifest.moves:
        if not move.completed:
            continue

        source = move.source
        destination = move.destination

        if source.exists() or source.is_symlink():
            reason = f"a file already exists at the original location: {source}"
            logger.error("Refusing to undo %s -> %s: %s", destination, source, reason)
            conflicts.append(UndoConflict(source=source, destination=destination, reason=reason))
            continue

        try:
            source.parent.mkdir(parents=True, exist_ok=True)
        except (PermissionError, FileNotFoundError, OSError) as exc:
            logger.error("Could not recreate directory %s: %s", source.parent, exc)
            conflicts.append(UndoConflict(source=source, destination=destination, reason=str(exc)))
            continue

        try:
            shutil.move(str(destination), str(source))
        except (FileNotFoundError, PermissionError, OSError) as exc:
            logger.error("Could not undo move %s -> %s: %s", destination, source, exc)
            conflicts.append(UndoConflict(source=source, destination=destination, reason=str(exc)))
            continue

        restored.append(CompletedMove(source=destination, destination=source, completed=True))

    return UndoResult(restored=tuple(restored), conflicts=tuple(conflicts))
