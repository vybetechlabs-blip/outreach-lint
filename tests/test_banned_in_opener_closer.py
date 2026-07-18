from conftest import DraftFactory

from outreach_lint.models import Config
from outreach_lint.rules.per_draft import banned_in_opener_closer


def test_clean_draft_has_no_findings(make_draft: DraftFactory, config: Config) -> None:
    assert banned_in_opener_closer(make_draft(), config) == []


def test_automation_in_opener_reports_position(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(body="We automate quoting for tile shops. The middle can say it. Talk soon.")
    findings = banned_in_opener_closer(draft, config)
    assert len(findings) == 1
    assert "opener" in findings[0].message


def test_automation_in_closer_reports_position(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(
        body="Saw the spring backlog note. Happy to compare. Automation could help there."
    )
    findings = banned_in_opener_closer(draft, config)
    assert len(findings) == 1
    assert "closer" in findings[0].message


def test_automation_mid_body_is_allowed_here(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(
        body="Saw the backlog note. Some shops automate the quote step. Curious what you do."
    )
    assert banned_in_opener_closer(draft, config) == []


def test_single_sentence_counts_as_opener_only(make_draft: DraftFactory, config: Config) -> None:
    findings = banned_in_opener_closer(make_draft(body="We automate quoting"), config)
    assert len(findings) == 1
    assert "opener" in findings[0].message
