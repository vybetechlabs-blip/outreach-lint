from conftest import DraftFactory

from outreach_lint.models import Config, Severity
from outreach_lint.rules.batch import sequence_no_reuse

OPENER = "Saw the June post about the second location."
CLOSER = "Open to comparing notes this week?"


def test_varied_sequence_passes(make_draft: DraftFactory, config: Config) -> None:
    batch = [
        make_draft(
            id="t1",
            touch="T1",
            sequence_id="seq-1",
            body=f"{OPENER} Middle of the first touch. {CLOSER}",
        ),
        make_draft(
            id="t2",
            touch="T2",
            sequence_id="seq-1",
            body="Bumping this gently. One pattern from other shops. Worth a one-line reply?",
        ),
    ]
    assert sequence_no_reuse(batch, config) == []


def test_reused_opener_and_closer_are_errors(make_draft: DraftFactory, config: Config) -> None:
    batch = [
        make_draft(
            id="t1", touch="T1", sequence_id="seq-1", body=f"{OPENER} First middle. {CLOSER}"
        ),
        make_draft(
            id="t2", touch="T2", sequence_id="seq-1", body=f"{OPENER} Second middle. {CLOSER}"
        ),
    ]
    findings = sequence_no_reuse(batch, config)
    assert len(findings) == 2
    assert {f.severity for f in findings} == {Severity.ERROR}
    kinds = {f.message.split()[0] for f in findings}
    assert kinds == {"opener", "closer"}
    assert all(f.draft_id == "t2" for f in findings)


def test_reuse_across_different_sequences_is_ignored_here(
    make_draft: DraftFactory, config: Config
) -> None:
    batch = [
        make_draft(id="a", touch="T1", sequence_id="seq-1", body=f"{OPENER} Mid. {CLOSER}"),
        make_draft(id="b", touch="T1", sequence_id="seq-2", body=f"{OPENER} Mid. {CLOSER}"),
    ]
    assert sequence_no_reuse(batch, config) == []


def test_drafts_without_sequence_id_are_skipped(make_draft: DraftFactory, config: Config) -> None:
    batch = [
        make_draft(id="a", touch="T1", body=f"{OPENER} Mid. {CLOSER}"),
        make_draft(id="b", touch="T2", body=f"{OPENER} Mid. {CLOSER}"),
    ]
    assert sequence_no_reuse(batch, config) == []
