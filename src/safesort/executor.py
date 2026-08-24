"""Execution of a previously built :class:`~safesort.models.SortPlan`.

This module contains the *only* code path in SafeSort that is allowed to
move files. Everything upstream (``scan``, ``classify``, ``build_plan``) is
read-only; ``apply_plan`` is what turns a plan into real filesystem
changes, and only when the caller (the ``apply`` CLI subcommand) explicitly
asks for it.

A batch of filesystem moves is not a database transaction: if one move
fails partway through (a vanished source file, a permission error, a full
disk...) the rest of the batch still gets attempted, and the caller gets an
honest per-move report of what actually happened.
"""

from __future__ import annotations

import logging
import shutil

from safesort.models import CompletedMove, SortPlan

logger = logging.getLogger(__name__)


def apply_plan(plan: SortPlan) -> list[CompletedMove]:
    """Execute every move in ``plan`` and report what actually happened.

    Each operation is handled independently: a failure on one move (source
    vanished, permission denied, destination directory could not be
    created, or the destination already exists) is recorded as a
    not-completed :class:`CompletedMove` with an explanatory ``error``, and
    the remaining operations are still attempted.

    Even though :func:`safesort.planner.build_plan` already avoids planning
    a collision, the destination is re-checked here immediately before the
    move: on POSIX, ``shutil.move`` (via ``os.rename``) would otherwise
    silently overwrite a file that appeared at the destination after the
    plan was built. SafeSort never overwrites silently, so a filled-in
    destination is treated as a failure for that one move rather than
    performed.
    """
    results: list[CompletedMove] = []

    for operation in plan.operations:
        source = operation.source
        destination = operation.destination

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
        except (PermissionError, FileNotFoundError, OSError) as exc:
            logger.error("Could not create directory %s: %s", destination.parent, exc)
            results.append(
                CompletedMove(source, destination, completed=False, error=str(exc))
            )
            continue

        if destination.exists() or destination.is_symlink():
            message = f"destination already exists: {destination}"
            logger.error("Refusing to overwrite existing destination: %s", destination)
            results.append(
                CompletedMove(source, destination, completed=False, error=message)
            )
            continue

        try:
            shutil.move(str(source), str(destination))
        except FileNotFoundError as exc:
            logger.error("Source vanished before it could be moved: %s (%s)", source, exc)
            results.append(
                CompletedMove(source, destination, completed=False, error=str(exc))
            )
        except PermissionError as exc:
            logger.error("Permission denied moving %s -> %s: %s", source, destination, exc)
            results.append(
                CompletedMove(source, destination, completed=False, error=str(exc))
            )
        except OSError as exc:
            logger.error("Could not move %s -> %s: %s", source, destination, exc)
            results.append(
                CompletedMove(source, destination, completed=False, error=str(exc))
            )
        else:
            logger.info("Moved %s -> %s", source, destination)
            results.append(CompletedMove(source, destination, completed=True))

    return results
