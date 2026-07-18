from conftest import DraftFactory

from outreach_lint.models import Config, Severity
from outreach_lint.rules.per_draft import spam_phrases


def test_clean_draft_has_no_findings(make_draft: DraftFactory, config: Config) -> None:
    assert spam_phrases(make_draft(), config) == []


def test_flags_each_phrase_with_span(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(body="This risk-free offer is a guarantee. Act now.")
    findings = spam_phrases(draft, config)
    hit_phrases = {f.message for f in findings}
    assert any("risk-free" in message for message in hit_phrases)
    assert any("guarantee" in message for message in hit_phrases)
    assert any("act now" in message for message in hit_phrases)
    assert all(f.severity is Severity.WARNING for f in findings)
    for finding in findings:
        assert finding.span is not None
        quoted = finding.message.split('"')[1]
        assert draft.body[finding.span.start : finding.span.end].lower() == quoted


def test_matches_whole_phrases_only(make_draft: DraftFactory, config: Config) -> None:
    # "freedom" contains "free" but must not match; "100%" must.
    draft = make_draft(body="Freedom matters. We are 100% sure.")
    findings = spam_phrases(draft, config)
    assert len(findings) == 1
    assert '"100%"' in findings[0].message


def test_flags_excessive_exclamations(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(body="Great news! It landed! Talk soon.")
    findings = spam_phrases(draft, config)
    assert len(findings) == 1
    assert "exclamation" in findings[0].message
    assert spam_phrases(make_draft(body="One bang! Only."), config) == []
