import pytest
from conftest import DraftFactory
from pydantic import ValidationError

from outreach_lint.models import BannedConstructionsConfig, Config
from outreach_lint.rules.per_draft import banned_constructions


def test_clean_draft_has_no_findings(make_draft: DraftFactory, config: Config) -> None:
    assert banned_constructions(make_draft(), config) == []


def test_seed_pattern_trips(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(body="Worth a look before scheduling becomes the constraint?")
    findings = banned_constructions(draft, config)
    assert len(findings) == 1
    assert "becomes the constraint" in findings[0].message
    assert findings[0].span is not None


def test_user_patterns_extend_the_rule(make_draft: DraftFactory, config: Config) -> None:
    config.rules.banned_constructions.patterns = [r"\bquick question\b"]
    draft = make_draft(body="Quick question about the spring backlog.")
    findings = banned_constructions(draft, config)
    assert len(findings) == 1
    # The shipped seed no longer applies once overridden.
    seeded = make_draft(body="Act before quoting becomes the constraint.")
    assert banned_constructions(seeded, config) == []


def test_invalid_regex_fails_at_config_time() -> None:
    with pytest.raises(ValidationError, match="invalid regex"):
        BannedConstructionsConfig(patterns=["[unclosed"])
