from conftest import DraftFactory

from outreach_lint.models import Config, Severity
from outreach_lint.rules.per_draft import t1_no_pitch

PITCHY_BODY = (
    "We offer a scheduling tool for shops like yours. "
    "Automating the quote step saves hours. "
    "Book a call and I can walk you through pricing."
)


def test_clean_t1_has_no_findings(make_draft: DraftFactory, config: Config) -> None:
    assert t1_no_pitch(make_draft(touch="T1"), config) == []


def test_pitch_and_automation_language_are_errors(make_draft: DraftFactory, config: Config) -> None:
    findings = t1_no_pitch(make_draft(body=PITCHY_BODY, touch="T1"), config)
    messages = " | ".join(f.message for f in findings)
    assert all(f.severity is Severity.ERROR for f in findings)
    assert "we offer" in messages
    assert "book a call" in messages
    assert "pricing" in messages
    assert "Automating" in messages


def test_rule_only_applies_to_t1(make_draft: DraftFactory, config: Config) -> None:
    assert t1_no_pitch(make_draft(body=PITCHY_BODY, touch="T2"), config) == []
    assert t1_no_pitch(make_draft(body=PITCHY_BODY, touch=None), config) == []


def test_all_automation_inflections_match(make_draft: DraftFactory, config: Config) -> None:
    for word in ("automate", "automates", "automated", "automation"):
        findings = t1_no_pitch(make_draft(body=f"We {word} things.", touch="T1"), config)
        assert len(findings) == 1, word
