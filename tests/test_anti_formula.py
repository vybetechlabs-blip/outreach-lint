from conftest import DraftFactory

from outreach_lint.models import Config
from outreach_lint.rules.batch import anti_formula


def _formula(trade: str, work: str) -> str:
    return (
        f"My guess is your crew is losing hours to quoting, not to the {work}. "
        f"Most {trade} shops I talk to hit this the season after a big hire. "
        "Open to comparing notes this week?"
    )


DIVERSE = [
    "Saw the second-location news. That usually reshuffles who owns estimates. Curious how "
    "you split it now.",
    "Your crew photos from the marina job were sharp. Nine slips in a month is moving. What "
    "does the quote backlog look like after a run like that?",
    "A shop owner I work with said spring intake broke their whiteboard system. Wondering if "
    "the same wall shows up for you.",
]


def test_diverse_batch_passes(make_draft: DraftFactory, config: Config) -> None:
    batch = [make_draft(id=f"d{i}", body=body) for i, body in enumerate(DIVERSE)]
    assert anti_formula(batch, config) == []


def test_shared_skeleton_reports_the_whole_cluster(
    make_draft: DraftFactory, config: Config
) -> None:
    batch = [
        make_draft(id="tile", body=_formula("tile", "installs")),
        make_draft(id="roof", body=_formula("roofing", "site work")),
        make_draft(id="deck", body=_formula("deck", "builds")),
        make_draft(id="fresh", body=DIVERSE[0]),
    ]
    findings = anti_formula(batch, config)
    flagged = {f.draft_id for f in findings}
    assert flagged == {"tile", "roof", "deck"}
    assert all("'tile'" in f.message and "'deck'" in f.message for f in findings)


def test_pairs_below_min_cluster_size_pass(make_draft: DraftFactory, config: Config) -> None:
    batch = [
        make_draft(id="tile", body=_formula("tile", "installs")),
        make_draft(id="roof", body=_formula("roofing", "site work")),
        make_draft(id="fresh", body=DIVERSE[0]),
    ]
    assert anti_formula(batch, config) == []
