from pathlib import Path

import pytest

from outreach_lint.config import ConfigError, load_config
from outreach_lint.models import Config


def test_shipped_toml_matches_model_defaults() -> None:
    """Guard against drift between default_config.toml and the Pydantic defaults."""
    assert load_config() == Config()


def test_user_overrides_merge_over_defaults(tmp_path: Path) -> None:
    user = tmp_path / "user.toml"
    user.write_text(
        """
[scoring]
warning = 15.0

[rules.length_band]
max_words = 140

[rules.reading_level]
enabled = false
""",
        encoding="utf-8",
    )
    config = load_config(user)
    assert config.scoring.warning == 15.0
    assert config.rules.length_band.max_words == 140
    assert config.rules.length_band.min_words == 40  # untouched default survives
    assert config.rules.reading_level.enabled is False
    assert config.rules.spam_phrases.enabled is True


def test_unknown_key_fails_loudly(tmp_path: Path) -> None:
    user = tmp_path / "user.toml"
    user.write_text("[rules.length_band]\nmax_wordz = 9\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="max_wordz"):
        load_config(user)


def test_invalid_toml_fails(tmp_path: Path) -> None:
    user = tmp_path / "user.toml"
    user.write_text("not = [valid", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(user)


def test_invalid_rule_regex_fails(tmp_path: Path) -> None:
    user = tmp_path / "user.toml"
    user.write_text('[rules.banned_constructions]\npatterns = ["[oops"]\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid regex"):
        load_config(user)


def test_missing_config_file_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="cannot read"):
        load_config(tmp_path / "nope.toml")
