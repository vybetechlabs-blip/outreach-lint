from conftest import DraftFactory

from outreach_lint.models import Config
from outreach_lint.rules.per_draft import hedge_count


def test_single_hedge_is_allowed(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(body="My guess is quoting slowed after the move. Curious if that lands.")
    assert hedge_count(draft, config) == []


def test_multiple_hedges_warn_and_are_listed(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(body="Maybe this is off. Perhaps quoting slowed, or I imagine it did.")
    findings = hedge_count(draft, config)
    assert len(findings) == 1
    message = findings[0].message
    assert "3 hedges" in message
    for hedge in ('"maybe"', '"perhaps"', '"i imagine"'):
        assert hedge in message


def test_matching_is_case_insensitive(make_draft: DraftFactory, config: Config) -> None:
    draft = make_draft(body="MAYBE it moved. Possibly not.")
    assert len(hedge_count(draft, config)) == 1


def test_limit_is_configurable(make_draft: DraftFactory, config: Config) -> None:
    config.rules.hedge_count.max_hedges = 3
    draft = make_draft(body="Maybe this is off. Perhaps quoting slowed, or I imagine it did.")
    assert hedge_count(draft, config) == []
