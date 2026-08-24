"""Read-only directory scanning.

:func:`scan` is one of SafeSort's three read-only commands (along with
``plan`` and ``duplicates``). It must never create, move, or delete
anything on disk — it only calls ``iterdir()`` / ``stat()`` / ``is_dir()``
/ ``is_symlink()``, all of which are pure reads.
"""

from __future__ import annotations

import logging
from pathlib import Path

from safesort.config import Config
from safesort.models import FileInfo

logger = logging.getLogger(__name__)


def scan(root: Path, config: Config) -> list[FileInfo]:
    """Recursively scan ``root`` and return a :class:`FileInfo` per file.

    Directories whose name is in ``config.excluded_names()`` (which always
    includes the configured destination directory) are skipped entirely,
    subtree and all. Symbolic links — both to files and to directories —
    are skipped and never followed, so SafeSort never moves a symlink and
    never walks into a symlinked directory (which could otherwise escape
    ``root`` or create a cycle).

    Directories that can't be listed (e.g. a permission error) are logged
    and skipped rather than aborting the whole scan.
    """
    root = Path(root)
    excluded = config.excluded_names()
    results: list[FileInfo] = []
    _scan_dir(root, excluded, results)
    return results


def _scan_dir(directory: Path, excluded: frozenset[str], results: list[FileInfo]) -> None:
    try:
        entries = list(directory.iterdir())
    except PermissionError:
        logger.warning("Permission denied, skipping directory: %s", directory)
        return
    except FileNotFoundError:
        logger.warning("Directory vanished during scan, skipping: %s", directory)
        return
    except OSError as exc:
        logger.warning("Could not read directory %s: %s", directory, exc)
        return

    for entry in entries:
        try:
            if entry.is_symlink():
                logger.info("Skipping symlink: %s", entry)
                continue
            if entry.is_dir():
                if entry.name in excluded:
                    logger.info("Skipping excluded directory: %s", entry)
                    continue
                _scan_dir(entry, excluded, results)
            elif entry.is_file():
                try:
                    size = entry.stat().st_size
                except (PermissionError, FileNotFoundError, OSError) as exc:
                    logger.warning("Could not stat file %s: %s", entry, exc)
                    continue
                results.append(
                    FileInfo(path=entry, size=size, extension=entry.suffix.lower())
                )
        except PermissionError:
            logger.warning("Permission denied, skipping: %s", entry)
            continue
        except OSError as exc:
            logger.warning("Could not inspect %s: %s", entry, exc)
            continue
