from conftest import DraftFactory

from outreach_lint.models import Config, Severity
from outreach_lint.rules.followup import followup_advances

GOOD_BUMP = (
    "Circling back in case this got buried. One thing I keep seeing across "
    "service shops: the slow step is approvals, not the estimate itself. "
    "No reply needed if the timing is wrong."
)


def test_t1_drafts_are_out_of_scope(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(touch="T1", body="Book a call about pricing today.")
    assert followup_advances([draft], config) == []


def test_clean_bump_passes(make_draft: DraftFactory, config: Config) -> None:
    assert followup_advances([make_draft(touch="T2", body=GOOD_BUMP)], config) == []


def test_repitching_followup_warns(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(touch="T3", body="Bumping this. Happy to book a call about pricing.")
    findings = followup_advances([draft], config)
    assert len(findings) == 2
    assert all(f.severity is Severity.WARNING for f in findings)
    assert all("re-pitches" in f.message for f in findings)


def test_assumption_escalation_warns(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(touch="T2", body="Clearly you meant to reply and it slipped.")
    findings = followup_advances([draft], config)
    assert len(findings) == 1
    assert "escalates assumptions" in findings[0].message


def test_reworded_t1_question_is_detected(make_draft: DraftFactory, config: Config) -> None:
    t1 = make_draft(
        id="t1",
        touch="T1",
        sequence_id="seq-9",
        body="Saw the new bay. How is quoting holding up this season?",
    )
    t2 = make_draft(
        id="t2",
        touch="T2",
        sequence_id="seq-9",
        body="Quick bump. How is quoting holding up this month?",
    )
    findings = followup_advances([t1, t2], config)
    assert len(findings) == 1
    assert findings[0].draft_id == "t2"
    assert "re-asks T1's question" in findings[0].message


def test_question_check_skips_without_t1_in_batch(make_draft: DraftFactory, config: Config) -> None:
    t2 = make_draft(
        id="t2",
        touch="T2",
        sequence_id="seq-9",
        body="Quick bump. How is quoting holding up this month?",
    )
    assert followup_advances([t2], config) == []
