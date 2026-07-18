from conftest import DraftFactory

from outreach_lint.models import Config, Draft
from outreach_lint.rules.batch import closer_round_robin

CLOSERS = {
    "a": "Open to comparing notes this week?",
    "b": "Worth a one-line reply if I'm off base?",
    "c": "Happy to trade what I'm seeing either way.",
}


def _batch(make_draft: DraftFactory, closer_keys: str) -> list[Draft]:
    return [
        make_draft(id=f"d{i}", body=f"Different opener number {i}. Middle text. {CLOSERS[key]}")
        for i, key in enumerate(closer_keys)
    ]


def test_full_rotation_passes(make_draft: DraftFactory, config: Config) -> None:
    # a, b, c, a: by the time 'a' repeats, two other closers have run (window 3).
    assert closer_round_robin(_batch(make_draft, "abca"), config) == []


def test_early_reuse_warns(make_draft: DraftFactory, config: Config) -> None:
    findings = closer_round_robin(_batch(make_draft, "aba"), config)
    assert len(findings) == 1
    assert findings[0].draft_id == "d2"
    assert "'d0'" in findings[0].message


def test_back_to_back_reuse_warns(make_draft: DraftFactory, config: Config) -> None:
    findings = closer_round_robin(_batch(make_draft, "aa"), config)
    assert len(findings) == 1


def test_window_is_configurable(make_draft: DraftFactory, config: Config) -> None:
    config.rules.closer_round_robin.window = 2
    # With window 2, alternating two closers is legal.
    assert closer_round_robin(_batch(make_draft, "abab"), config) == []
