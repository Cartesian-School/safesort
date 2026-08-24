"""Tests for safesort.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from safesort.config import Config, ConfigError, DEFAULT_DESTINATION, DEFAULT_EXCLUDE, load_config


def test_default_config_has_expected_values() -> None:
    config = Config()
    assert config.destination == DEFAULT_DESTINATION
    assert set(config.exclude) == set(DEFAULT_EXCLUDE)
    assert "documents" in config.extensions
    assert "other" not in config.extensions  # "other" is a fallback, not a configured category


def test_load_config_with_no_file_returns_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path)
    assert config.destination == DEFAULT_DESTINATION
    assert set(config.exclude) == set(DEFAULT_EXCLUDE)


def test_excluded_names_always_includes_destination_even_if_not_listed(tmp_path: Path) -> None:
    config = Config(destination="Sorted", exclude=(".git",))
    names = config.excluded_names()
    assert "Sorted" in names
    assert ".git" in names


def test_excluded_names_always_includes_state_dir() -> None:
    config = Config()
    assert ".safesort" in config.excluded_names()


def test_load_config_reads_toml_overrides(tmp_path: Path) -> None:
    (tmp_path / "safesort.toml").write_text(
        """
        destination = "Organized"
        exclude = [".git", "node_modules"]

        [extensions]
        documents = [".pdf", ".docx", ".txt"]
        images = [".jpg", ".jpeg", ".png", ".webp"]
        """,
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    assert config.destination == "Organized"
    assert set(config.exclude) == {".git", "node_modules"}
    assert config.extensions == {
        "documents": [".pdf", ".docx", ".txt"],
        "images": [".jpg", ".jpeg", ".png", ".webp"],
    }


def test_load_config_with_partial_toml_uses_defaults_for_missing_fields(tmp_path: Path) -> None:
    (tmp_path / "safesort.toml").write_text('destination = "Organized"\n', encoding="utf-8")
    config = load_config(tmp_path)
    assert config.destination == "Organized"
    assert set(config.exclude) == set(DEFAULT_EXCLUDE)


def test_load_config_with_malformed_toml_raises_config_error(tmp_path: Path) -> None:
    (tmp_path / "safesort.toml").write_text("this is not [valid toml", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_load_config_with_invalid_destination_type_raises_config_error(tmp_path: Path) -> None:
    (tmp_path / "safesort.toml").write_text("destination = 42\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_load_config_with_invalid_exclude_type_raises_config_error(tmp_path: Path) -> None:
    (tmp_path / "safesort.toml").write_text('exclude = "not-a-list"\n', encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(tmp_path)
