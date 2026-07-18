"""Load the shipped default config and deep-merge an optional user TOML over it.

The merged mapping is validated through :class:`outreach_lint.models.Config`
(``extra="forbid"`` throughout), so an unknown key or malformed value in a user
config raises :class:`ConfigError` instead of being silently ignored.
"""

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from outreach_lint.models import Config


class ConfigError(Exception):
    """Raised when a config file cannot be read, parsed, or validated."""


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Return ``base`` with ``override`` merged in; nested dicts merge, scalars replace."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"cannot read config file {path}: {exc}") from exc
    try:
        return tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from exc


def default_config_dict() -> dict[str, Any]:
    """The shipped ``default_config.toml`` as a plain mapping."""
    raw = resources.files("outreach_lint").joinpath("default_config.toml").read_text("utf-8")
    return tomllib.loads(raw)


def load_config(user_config_path: Path | None = None) -> Config:
    """Build the effective config: shipped defaults, then the user file on top."""
    merged = default_config_dict()
    if user_config_path is not None:
        merged = _deep_merge(merged, _load_toml(user_config_path))
    try:
        return Config.model_validate(merged)
    except ValidationError as exc:
        source = user_config_path or "default config"
        raise ConfigError(f"invalid configuration ({source}):\n{exc}") from exc
