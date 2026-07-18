from conftest import DraftFactory

from outreach_lint.models import Config
from outreach_lint.rules.per_draft import reading_level

DENSE_BODY = (
    "Considering the multifaceted organizational transformation initiatives "
    "currently underway across your distributed manufacturing operations, a "
    "comprehensive reevaluation of interdepartmental communication "
    "methodologies represents an extraordinarily consequential undertaking "
    "warranting immediate prioritization notwithstanding implementation "
    "complexities."
)


def test_conversational_draft_passes(make_draft: DraftFactory, config: Config) -> None:
    assert reading_level(make_draft(), config) == []


def test_dense_prose_trips_both_thresholds(make_draft: DraftFactory, config: Config) -> None:
    findings = reading_level(make_draft(body=DENSE_BODY), config)
    messages = " | ".join(f.message for f in findings)
    assert "grade level" in messages
    assert "over-polished" in messages


def test_empty_body_is_skipped(make_draft: DraftFactory, config: Config) -> None:
    assert reading_level(make_draft(body=""), config) == []


def test_ceiling_is_configurable(make_draft: DraftFactory, config: Config) -> None:
    config.rules.reading_level.max_grade = 1.0
    config.rules.reading_level.min_reading_ease = 0.0
    findings = reading_level(make_draft(), config)
    assert len(findings) == 1
    assert "grade level" in findings[0].message
