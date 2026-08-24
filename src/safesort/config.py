"""SafeSort configuration: sensible defaults plus an optional TOML overlay.

No configuration file is ever required. Every field has a built-in default,
so running any SafeSort command against a directory with no config file
present behaves predictably out of the box. When a config file *is* found,
it may override the destination directory name, the list of excluded
directory names, and the extension-to-category mapping used by the
classifier.

The config file is read-only: SafeSort never writes TOML.
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

#: Default destination directory (relative to the scanned root) that sorted
#: files are moved into.
DEFAULT_DESTINATION = "Sorted"

#: Default directory names that are always skipped while scanning.
DEFAULT_EXCLUDE: tuple[str, ...] = (".git", ".venv")

#: Default extension -> category mapping used by the classifier.
DEFAULT_EXTENSIONS: dict[str, list[str]] = {
    "documents": [".pdf", ".docx", ".txt", ".odt"],
    "images": [".jpg", ".jpeg", ".png", ".webp"],
    "video": [".mp4", ".mkv", ".mov"],
    "audio": [".mp3", ".wav", ".flac"],
    "archives": [".zip", ".tar", ".gz", ".7z"],
    "code": [".py", ".js", ".ts", ".rs", ".java"],
    "data": [".json", ".csv", ".xml"],
}

#: Name of the optional config file, if present in the scanned root.
CONFIG_FILENAME = "safesort.toml"

#: Directory SafeSort keeps its own bookkeeping (operation manifests) in.
#: Always excluded from scanning, just like the destination directory, so
#: SafeSort never treats its own manifests as sortable input.
STATE_DIRNAME = ".safesort"


@dataclass(frozen=True)
class Config:
    """Effective SafeSort configuration for a run.

    Attributes:
        destination: Name of the directory (relative to the scanned root)
            that sorted files are moved into. Defaults to ``"Sorted"``.
        exclude: Directory names that are skipped entirely while scanning,
            in addition to the destination directory (which is always
            excluded, regardless of whether it appears in this tuple).
        extensions: Mapping of category name to a list of lower-cased
            extensions (each including the leading dot).
    """

    destination: str = DEFAULT_DESTINATION
    exclude: tuple[str, ...] = field(default_factory=lambda: DEFAULT_EXCLUDE)
    extensions: dict[str, list[str]] = field(
        default_factory=lambda: {k: list(v) for k, v in DEFAULT_EXTENSIONS.items()}
    )

    def excluded_names(self) -> frozenset[str]:
        """Directory names to skip: configured excludes plus internals.

        The destination directory and SafeSort's own ``.safesort`` state
        directory are always excluded dynamically, regardless of what's in
        ``exclude``, so a second ``scan``/``plan``/``apply`` run never
        re-processes already-sorted files or SafeSort's own manifests.
        """
        return frozenset({*self.exclude, self.destination, STATE_DIRNAME})


class ConfigError(Exception):
    """Raised when a SafeSort config file exists but cannot be parsed."""


def load_config(root: Path) -> Config:
    """Load configuration for ``root``, falling back to defaults.

    Looks for ``safesort.toml`` directly inside ``root``. If it is not
    present, the built-in defaults are returned untouched. If it is present
    but malformed, :class:`ConfigError` is raised with a clear message
    rather than propagating a raw ``tomllib`` traceback.
    """
    config_path = root / CONFIG_FILENAME
    if not config_path.is_file():
        return Config()

    try:
        with config_path.open("rb") as handle:
            raw = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Could not parse config file {config_path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Could not read config file {config_path}: {exc}") from exc

    destination = raw.get("destination", DEFAULT_DESTINATION)
    if not isinstance(destination, str) or not destination:
        raise ConfigError(
            f"Invalid 'destination' in {config_path}: expected a non-empty string"
        )

    exclude_raw = raw.get("exclude", list(DEFAULT_EXCLUDE))
    if not isinstance(exclude_raw, list) or not all(isinstance(x, str) for x in exclude_raw):
        raise ConfigError(f"Invalid 'exclude' in {config_path}: expected a list of strings")
    exclude = tuple(exclude_raw)

    extensions_raw = raw.get("extensions", DEFAULT_EXTENSIONS)
    if not isinstance(extensions_raw, dict):
        raise ConfigError(f"Invalid '[extensions]' table in {config_path}")
    extensions: dict[str, list[str]] = {}
    for category, exts in extensions_raw.items():
        if not isinstance(exts, list) or not all(isinstance(x, str) for x in exts):
            raise ConfigError(
                f"Invalid extension list for category {category!r} in {config_path}"
            )
        extensions[category] = list(exts)

    logger.info("Loaded config from %s", config_path)
    return Config(destination=destination, exclude=exclude, extensions=extensions)
