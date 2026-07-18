"""Batch rules: operate across a set of drafts to catch templating patterns
invisible at the single-draft level.

Openers and closers are compared on normalized text (lowercased, punctuation
stripped) so trivial punctuation edits don't defeat the checks.
"""

from __future__ import annotations

from collections.abc import Sequence

from outreach_lint.models import TOUCH_ORDER, Config, Draft, Finding, Severity
from outreach_lint.rules import rule
from outreach_lint.textutil import jaccard, ngrams, normalize, sentences, words


def _opener(draft: Draft) -> str:
    sents = sentences(draft.body)
    return normalize(sents[0].text) if sents else ""


def _closer(draft: Draft) -> str:
    sents = sentences(draft.body)
    return normalize(sents[-1].text) if sents else ""


@rule("opener_variety", scope="batch")
def opener_variety(drafts: Sequence[Draft], config: Config) -> list[Finding]:
    """Warn when two drafts open with near-identical constructions.

    Similarity is Jaccard overlap of token n-grams over the normalized first
    sentence; the finding attaches to the later draft and names the pair.
    """
    cfg = config.rules.opener_variety
    openers = [(draft, ngrams(words(_opener(draft)), cfg.ngram_size)) for draft in drafts]
    findings: list[Finding] = []
    for j in range(len(openers)):
        for i in range(j):
            earlier_draft, earlier_grams = openers[i]
            later_draft, later_grams = openers[j]
            similarity = jaccard(earlier_grams, later_grams)
            if similarity >= cfg.similarity_threshold:
                findings.append(
                    Finding(
                        rule_id="opener_variety",
                        severity=Severity.WARNING,
                        message=(
                            f"opener nearly identical to draft '{earlier_draft.id}' "
                            f"(similarity {similarity:.2f})"
                        ),
                        draft_id=later_draft.id,
                    )
                )
    return findings


@rule("closer_round_robin", scope="batch")
def closer_round_robin(drafts: Sequence[Draft], config: Config) -> list[Finding]:
    """Closers must rotate: a closer may not repeat until ``window - 1`` other
    closers have been used since (rolling window over batch order)."""
    cfg = config.rules.closer_round_robin
    findings: list[Finding] = []
    recent: list[tuple[str, str]] = []  # (normalized closer, draft id), most recent last
    for draft in drafts:
        closer = _closer(draft)
        if closer:
            for seen_closer, seen_id in recent:
                if closer == seen_closer:
                    findings.append(
                        Finding(
                            rule_id="closer_round_robin",
                            severity=Severity.WARNING,
                            message=(
                                f"closer reused from draft '{seen_id}' before "
                                f"{cfg.window - 1} other closers ran"
                            ),
                            draft_id=draft.id,
                        )
                    )
                    break
            recent.append((closer, draft.id))
            if len(recent) > cfg.window - 1:
                recent.pop(0)
    return findings


@rule("sequence_no_reuse", scope="batch")
def sequence_no_reuse(drafts: Sequence[Draft], config: Config) -> list[Finding]:
    """Within one prospect's sequence (same ``sequence_id``), no opener or
    closer may be reused across touches. Repeats are errors."""
    del config
    findings: list[Finding] = []
    sequences: dict[str, list[Draft]] = {}
    for draft in drafts:
        if draft.sequence_id:
            sequences.setdefault(draft.sequence_id, []).append(draft)
    for members in sequences.values():
        ordered = sorted(members, key=lambda d: TOUCH_ORDER.get(d.touch or "", 99))
        seen: dict[tuple[str, str], Draft] = {}
        for draft in ordered:
            for kind, text in (("opener", _opener(draft)), ("closer", _closer(draft))):
                if not text:
                    continue
                key = (kind, text)
                if key in seen:
                    findings.append(
                        Finding(
                            rule_id="sequence_no_reuse",
                            severity=Severity.ERROR,
                            message=(
                                f"{kind} reused within sequence "
                                f"'{draft.sequence_id}' (first used in "
                                f"'{seen[key].id}')"
                            ),
                            draft_id=draft.id,
                        )
                    )
                else:
                    seen[key] = draft
    return findings


@rule("anti_formula", scope="batch")
def anti_formula(drafts: Sequence[Draft], config: Config) -> list[Finding]:
    """Detect drafts sharing a structural formula (e.g. the same
    "my guess is + pain hypothesis" skeleton in the opening move).

    The opening move is the first ``prefix_words`` words, normalized; drafts
    whose n-gram overlap clears the threshold are linked, and connected
    clusters of ``min_cluster_size`` or more are reported so the whole group
    can be de-templated together.
    """
    cfg = config.rules.anti_formula
    grams = [
        ngrams(words(normalize(draft.body))[: cfg.prefix_words], cfg.ngram_size) for draft in drafts
    ]
    # Union-find over similarity edges.
    parent = list(range(len(drafts)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for j in range(len(drafts)):
        for i in range(j):
            if jaccard(grams[i], grams[j]) >= cfg.similarity_threshold:
                parent[find(i)] = find(j)

    clusters: dict[int, list[Draft]] = {}
    for index, draft in enumerate(drafts):
        clusters.setdefault(find(index), []).append(draft)

    findings: list[Finding] = []
    for members in clusters.values():
        if len(members) < cfg.min_cluster_size:
            continue
        ids = ", ".join(f"'{member.id}'" for member in members)
        for member in members:
            findings.append(
                Finding(
                    rule_id="anti_formula",
                    severity=Severity.WARNING,
                    message=f"shares a structural formula with {len(members) - 1} "
                    f"other draft(s): {ids}",
                    draft_id=member.id,
                )
            )
    return findings
