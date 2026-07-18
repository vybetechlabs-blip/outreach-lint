from conftest import DraftFactory

from outreach_lint.models import Config
from outreach_lint.rules.per_draft import length_band


def test_clean_draft_inside_band(make_draft: DraftFactory, config: Config) -> None:
    assert length_band(make_draft(), config) == []


def test_too_short_warns(make_draft: DraftFactory, config: Config) -> None:
    findings = length_band(make_draft(body="Quick one. Free Friday?"), config)
    assert len(findings) == 1
    assert "too short" in findings[0].message


def test_too_long_warns(make_draft: DraftFactory, config: Config) -> None:
    findings = length_band(make_draft(body="word " * 130), config)
    assert len(findings) == 1
    assert "too long" in findings[0].message


def test_band_boundaries_are_inclusive(make_draft: DraftFactory, config: Config) -> None:
    config.rules.length_band.min_words = 5
    config.rules.length_band.max_words = 6
    assert length_band(make_draft(body="one two three four five"), config) == []
    assert length_band(make_draft(body="one two three four five six"), config) == []
    assert len(length_band(make_draft(body="one two three four"), config)) == 1
    assert len(length_band(make_draft(body="one two three four five six seven"), config)) == 1
