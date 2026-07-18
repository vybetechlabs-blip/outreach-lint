from conftest import DraftFactory

from outreach_lint.models import Config, Severity
from outreach_lint.rules.per_draft import unfilled_tokens


def test_clean_draft_has_no_findings(make_draft: DraftFactory, config: Config) -> None:
    assert unfilled_tokens(make_draft(), config) == []


def test_flags_every_token_style_as_error(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(
        body="Hi {first_name}, saw {{company}} uses [[hook]] and %CITY% at <<plan>>."
    )
    findings = unfilled_tokens(draft, config)
    tokens = {f.message for f in findings}
    assert len(findings) == 5
    assert all(f.severity is Severity.ERROR for f in findings)
    for token in ("{first_name}", "{{company}}", "[[hook]]", "%CITY%", "<<plan>>"):
        assert any(token in message for message in tokens)


def test_nested_braces_report_once(make_draft: DraftFactory, config: Config) -> None:
    # {{first_name}} contains {first_name}; only the widest match should report.
    findings = unfilled_tokens(make_draft(body="Hi {{first_name}}, quick one."), config)
    assert len(findings) == 1
    assert "{{first_name}}" in findings[0].message


def test_plain_percentages_do_not_match(make_draft: DraftFactory, config: Config) -> None:
    findings = unfilled_tokens(make_draft(body="Margins moved 5% to 8% last spring."), config)
    assert findings == []
