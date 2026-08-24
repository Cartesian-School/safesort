"""Extension-based file classification.

Classification here is a heuristic based purely on the filename extension —
it is not proof of a file's actual content (a ``.txt`` file could contain
anything). That is a deliberate, documented tradeoff: inspecting file
content would be slower, more invasive, and out of scope for a tool whose
job is organizing files by what they claim to be.
"""

from __future__ import annotations

#: Category used for any extension that doesn't match a configured category.
OTHER_CATEGORY = "other"


def classify(extension: str, mapping: dict[str, list[str]]) -> str:
    """Return the category name for a given file extension.

    Matching is case-insensitive. ``extension`` should include the leading
    dot (e.g. ``".JPG"``), matching what :class:`safesort.models.FileInfo`
    stores. If no category in ``mapping`` claims the extension, the
    :data:`OTHER_CATEGORY` fallback (``"other"``) is returned.
    """
    normalized = extension.lower()
    for category, extensions in mapping.items():
        lowered = {ext.lower() for ext in extensions}
        if normalized in lowered:
            return category
    return OTHER_CATEGORY
