"""Read-only duplicate-content detection.

Detection is staged so that expensive work is only ever done when it can
actually change the answer:

1. Group files by size. Files with a unique size cannot have a duplicate.
2. For every size group with 2+ files, hash each file's content with
   SHA-256, reading it in fixed-size chunks so a large file is never
   loaded into memory all at once.
3. Group by ``(size, digest)``.
4. For any resulting group with 2+ files, confirm it byte by byte
   (:func:`files_equal`) before reporting it as a duplicate group. A
   SHA-256 collision between two different files is astronomically
   unlikely, but this tool's job is deciding which of a user's real files
   get treated as interchangeable, so the digest alone is treated as a
   fast filter, never as the final answer.

This module only ever *reports* duplicate groups — it has no delete code
path at all, not even a disabled or future one.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from pathlib import Path

from safesort.models import DuplicateGroup, FileInfo

logger = logging.getLogger(__name__)

#: Default chunk size used when incrementally hashing file contents.
DEFAULT_CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """Compute the SHA-256 hex digest of ``path``'s contents.

    Reads the file in ``chunk_size``-byte chunks rather than loading it
    into memory all at once, so this scales to files much larger than
    available RAM.
    """
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def files_equal(path_a: Path, path_b: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> bool:
    """Compare two files' contents chunk by chunk, never loading either
    fully into memory. This is SafeSort's final confirmation step after two
    files' SHA-256 digests already match — see the module docstring for why
    a matching digest alone is not treated as proof."""
    with path_a.open("rb") as file_a, path_b.open("rb") as file_b:
        while True:
            chunk_a = file_a.read(chunk_size)
            chunk_b = file_b.read(chunk_size)
            if chunk_a != chunk_b:
                return False
            if not chunk_a:
                return True


def find_duplicates(
    files: list[FileInfo], chunk_size: int = DEFAULT_CHUNK_SIZE
) -> list[DuplicateGroup]:
    """Return groups of files whose content is byte-for-byte identical.

    Read-only: this only opens files for reading. Files that can no longer
    be read (removed or permission-denied between scanning and hashing)
    are logged and skipped rather than aborting the whole scan.
    """
    by_size: dict[int, list[FileInfo]] = defaultdict(list)
    for file in files:
        by_size[file.size].append(file)

    groups: list[DuplicateGroup] = []
    for size, candidates in by_size.items():
        if len(candidates) < 2:
            continue

        by_digest: dict[str, list[FileInfo]] = defaultdict(list)
        for candidate in candidates:
            try:
                digest = sha256_file(candidate.path, chunk_size)
            except (PermissionError, FileNotFoundError, OSError) as exc:
                logger.warning("Could not hash %s, skipping: %s", candidate.path, exc)
                continue
            by_digest[digest].append(candidate)

        for digest, matched in by_digest.items():
            if len(matched) < 2:
                continue
            confirmed = [matched[0]]
            for candidate in matched[1:]:
                try:
                    if files_equal(matched[0].path, candidate.path, chunk_size):
                        confirmed.append(candidate)
                    else:
                        logger.warning(
                            "SHA-256 digest matched but bytes differ for %s and %s "
                            "(hash collision or file changed after hashing); excluding from duplicate group",
                            matched[0].path,
                            candidate.path,
                        )
                except (PermissionError, FileNotFoundError, OSError) as exc:
                    logger.warning("Could not confirm %s against %s, skipping: %s", candidate.path, matched[0].path, exc)
            if len(confirmed) >= 2:
                groups.append(DuplicateGroup(size=size, digest=digest, files=tuple(confirmed)))

    return groups
