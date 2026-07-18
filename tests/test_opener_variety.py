from conftest import DraftFactory

from outreach_lint.models import Config
from outreach_lint.rules.batch import opener_variety

OPENER_A = "My guess is your crew is losing hours to quoting, not to the installs."
OPENER_A_VARIANT = "My guess is your crew is losing hours to quoting, not to the site work."


def test_distinct_openers_pass(make_draft: DraftFactory, config: Config) -> None:
    batch = [
        make_draft(id="a", body="Saw the note about the spring rush. Curious how it went."),
        make_draft(id="b", body="Your hiring post stood out. Nine crews is a real jump."),
    ]
    assert opener_variety(batch, config) == []


def test_near_identical_openers_warn_on_the_later_draft(
    make_draft: DraftFactory, config: Config
) -> None:
    batch = [
        make_draft(id="first", body=f"{OPENER_A} Rest of this one differs."),
        make_draft(id="second", body=f"{OPENER_A_VARIANT} Completely different middle."),
    ]
    findings = opener_variety(batch, config)
    assert len(findings) == 1
    assert findings[0].draft_id == "second"
    assert "'first'" in findings[0].message


def test_single_draft_batch_passes(make_draft: DraftFactory, config: Config) -> None:
    assert opener_variety([make_draft()], config) == []


def test_threshold_is_configurable(make_draft: DraftFactory, config: Config) -> None:
    config.rules.opener_variety.similarity_threshold = 1.01  # nothing can clear it
    batch = [
        make_draft(id="first", body=f"{OPENER_A} Middle one."),
        make_draft(id="second", body=f"{OPENER_A} Middle two."),
    ]
    assert opener_variety(batch, config) == []
