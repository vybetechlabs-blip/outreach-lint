from pathlib import Path

from conftest import DraftFactory

from outreach_lint.linter import lint_batch, lint_one, score_draft
from outreach_lint.loader import load_path
from outreach_lint.models import Config, Finding, Severity

EXAMPLES = Path(__file__).parent.parent / "examples"


def _finding(rule_id: str, severity: Severity) -> Finding:
    return Finding(rule_id=rule_id, severity=severity, message="m", draft_id="d")


def test_score_deducts_severity_weights(config: Config) -> None:
    findings = [
        _finding("unfilled_tokens", Severity.ERROR),  # -25
        _finding("spam_phrases", Severity.WARNING),  # -10
        _finding("voice_check", Severity.INFO),  # -3
    ]
    assert score_draft(findings, config) == 62


def test_score_clamps_at_zero(config: Config) -> None:
    findings = [_finding("unfilled_tokens", Severity.ERROR)] * 5
    assert score_draft(findings, config) == 0


def test_rule_weight_override_beats_severity_weight(config: Config) -> None:
    config.rules.spam_phrases.weight = 50.0
    assert score_draft([_finding("spam_phrases", Severity.WARNING)], config) == 50


def test_disabled_rules_do_not_run(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(body="Hi {{first_name}}, super short one.")
    assert any(f.rule_id == "unfilled_tokens" for f in lint_one(draft, config).findings)
    config.rules.unfilled_tokens.enabled = False
    assert not any(f.rule_id == "unfilled_tokens" for f in lint_one(draft, config).findings)


def test_batch_findings_attach_to_the_right_draft(make_draft: DraftFactory, config: Config) -> None:
    opener = "My guess is your crew is losing hours to quoting, not to the installs."
    batch = [
        make_draft(id="first", body=f"{opener} Unique middle one here. Unique closer one."),
        make_draft(id="second", body=f"{opener} Very different middle. Another closer."),
    ]
    report = lint_batch(batch, config)
    second = next(r for r in report.reports if r.draft_id == "second")
    first = next(r for r in report.reports if r.draft_id == "first")
    assert any(f.rule_id == "opener_variety" for f in second.findings)
    assert not any(f.rule_id == "opener_variety" for f in first.findings)


def test_extra_findings_score_like_rule_findings(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(id="draft-1")
    clean = lint_one(draft, config)
    assert clean.score == 100
    extra = [
        Finding(
            rule_id="voice_check",
            severity=Severity.WARNING,
            message="voice: grounding scored 1/5",
            draft_id="draft-1",
        )
    ]
    report = lint_batch([draft], config, extra_findings=extra).reports[0]
    assert report.score == 90
    assert len(report.findings) == 1


CLEAN_BODY_B = (
    "Congrats on the marina build wrapping early — word is the punch list was "
    "short, which almost never happens on a first slip job. What are you "
    "lining up for the fall season, and does the crew stay together through "
    "winter? Either way, nice work on that one."
)


def test_batch_report_aggregates(make_draft: DraftFactory, config: Config) -> None:
    # Two clean but *different* drafts: identical bodies would (correctly)
    # trip the batch templating rules.
    report = lint_batch([make_draft(id="a"), make_draft(id="b", body=CLEAN_BODY_B)], config)
    assert report.draft_count == 2
    assert report.mean_score == 100.0
    assert report.total_findings == 0


def test_example_good_t1_scores_100(config: Config) -> None:
    draft = load_path(EXAMPLES / "good_t1.md")[0]
    report = lint_one(draft, config)
    assert report.findings == []
    assert report.score == 100


def test_example_templated_batch_trips_the_batch_rules(config: Config) -> None:
    drafts = load_path(EXAMPLES / "templated_batch.jsonl")
    report = lint_batch(drafts, config)
    fired = {f.rule_id for r in report.reports for f in r.findings}
    # The deliberately-bad example must keep tripping the templating detectors.
    assert {"anti_formula", "opener_variety", "sequence_no_reuse", "closer_round_robin"} <= fired
    assert {"unfilled_tokens", "t1_no_pitch", "followup_advances"} <= fired
