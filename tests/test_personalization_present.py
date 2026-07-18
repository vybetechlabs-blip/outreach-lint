from conftest import DraftFactory

from outreach_lint.models import Config, Severity
from outreach_lint.rules.per_draft import personalization_present

GENERIC_BODY = (
    "Hope you are doing well. Wanted to reach out about something that might "
    "matter to a shop like yours. It seems like a busy season. Would love to hear back."
)


def test_populated_hook_satisfies_the_rule(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(body=GENERIC_BODY, hook="their April hiring spree")
    assert personalization_present(draft, config) == []


def test_generic_body_without_hook_warns(make_draft: DraftFactory, config: Config) -> None:
    findings = personalization_present(make_draft(body=GENERIC_BODY, hook=None), config)
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARNING


def test_specific_reference_in_body_counts(make_draft: DraftFactory, config: Config) -> None:
    quoted = make_draft(body='Your line about "quoting by hand" stuck with me.', hook=None)
    numbered = make_draft(body="Going from 4 crews to 9 in a spring is quick.", hook=None)
    assert personalization_present(quoted, config) == []
    assert personalization_present(numbered, config) == []


def test_whitespace_hook_does_not_count(make_draft: DraftFactory, config: Config) -> None:
    findings = personalization_present(make_draft(body=GENERIC_BODY, hook="   "), config)
    assert len(findings) == 1
