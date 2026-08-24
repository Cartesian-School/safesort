"""Pure, non-destructive planning of file moves.

:func:`build_plan` never modifies the filesystem. The only filesystem
interaction it performs is a read-only existence check (``Path.exists()``)
used to make sure a planned destination doesn't collide with a file that is
already there. It's the second of SafeSort's three read-only commands.
"""

from __future__ import annotations

from pathlib import Path

from safesort.classifier import classify
from safesort.config import Config
from safesort.models import FileInfo, MoveOperation, SortPlan


def build_plan(files: list[FileInfo], root: Path, config: Config) -> SortPlan:
    """Build a :class:`SortPlan` that organizes ``files`` under ``root``.

    Each file is classified by extension and assigned a destination of
    ``root / config.destination / category / filename``. If that name is
    already taken — either by a real file already on disk, or by another
    operation already queued earlier in this same plan — a safe alternative
    name is generated using the ``name (1).ext``, ``name (2).ext``, ...
    pattern until a free name is found. Existing files are never
    overwritten and two queued operations never target the same
    destination.
    """
    root = Path(root)
    dest_root = root / config.destination
    reserved: set[Path] = set()
    operations: list[MoveOperation] = []

    for file in files:
        category = classify(file.extension, config.extensions)
        dest_dir = dest_root / category
        candidate = dest_dir / file.path.name
        destination = _resolve_collision(candidate, reserved)
        reserved.add(destination)
        operations.append(MoveOperation(source=file.path, destination=destination))

    return SortPlan(root=root, operations=tuple(operations))


def _resolve_collision(candidate: Path, reserved: set[Path]) -> Path:
    """Return ``candidate`` if free, otherwise the first free ``name (n).ext``."""
    if candidate not in reserved and not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    parent = candidate.parent
    counter = 1
    while True:
        alternative = parent / f"{stem} ({counter}){suffix}"
        if alternative not in reserved and not alternative.exists():
            return alternative
        counter += 1
