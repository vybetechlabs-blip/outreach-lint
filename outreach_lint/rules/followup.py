"""``followup_advances``: a follow-up touch must advance the thread, not repeat it.

This rule is necessarily heuristic. What "advancing" means (a genuine bump, a
new cross-client pattern-insight, lower reply friction) is a judgment call no
static check can make reliably, so this module only flags the *negative*
signals it can detect with reasonable precision, and stays a ``warning``,
never an ``error``:

* **Re-pitching** — pitch/CTA phrases from the configured lexicon appearing in
  a T2-T4 draft. Follow-ups that pitch read as pressure, not progress.
* **Assumption escalation** — cue phrases ("clearly you", "I know you", ...)
  that assert more certainty about the prospect than a T1 could have earned.
* **Re-asked questions** — question sentences whose normalized n-gram overlap
  with a question in the same sequence's T1 clears a threshold, i.e. T1's ask
  reworded. This sub-check needs the T1 draft in the same linted batch (matched
  via ``sequence_id``) and silently skips when it isn't there.

Registered as a batch rule purely so it can see the sequence's T1; every
finding is per-draft and the rule behaves per-draft in all other respects.
"""

from __future__ import annotations

from collections.abc import Sequence

from outreach_lint.models import Config, Draft, Finding, Severity, Span
from outreach_lint.rules import rule
from outreach_lint.textutil import (
    jaccard,
    line_of,
    ngrams,
    normalize,
    phrase_spans,
    sentences,
    words,
)

_QUESTION_NGRAM_SIZE = 2


def _questions(draft: Draft) -> list[str]:
    return [s.text for s in sentences(draft.body) if s.text.rstrip().endswith("?")]


@rule("followup_advances", scope="batch")
def followup_advances(drafts: Sequence[Draft], config: Config) -> list[Finding]:
    cfg = config.rules.followup_advances
    t1_by_sequence: dict[str, Draft] = {
        draft.sequence_id: draft for draft in drafts if draft.touch == "T1" and draft.sequence_id
    }
    findings: list[Finding] = []
    for draft in drafts:
        if draft.touch in (None, "T1"):
            continue
        for phrase in cfg.pitch_phrases:
            for start, end in phrase_spans(draft.body, phrase):
                findings.append(
                    Finding(
                        rule_id="followup_advances",
                        severity=Severity.WARNING,
                        message=f'follow-up re-pitches instead of advancing: "{phrase}"',
                        draft_id=draft.id,
                        span=_finding_span(draft, start, end),
                    )
                )
        for cue in cfg.escalation_cues:
            for start, end in phrase_spans(draft.body, cue):
                findings.append(
                    Finding(
                        rule_id="followup_advances",
                        severity=Severity.WARNING,
                        message=(f'follow-up escalates assumptions beyond T1: "{cue}"'),
                        draft_id=draft.id,
                        span=_finding_span(draft, start, end),
                    )
                )
        t1 = t1_by_sequence.get(draft.sequence_id or "")
        if t1 is not None:
            findings.extend(_restated_questions(draft, t1, cfg.question_similarity_threshold))
    return findings


def _finding_span(draft: Draft, start: int, end: int) -> Span:
    return Span(start=start, end=end, line=line_of(start, draft.body))


def _restated_questions(draft: Draft, t1: Draft, threshold: float) -> list[Finding]:
    t1_question_grams = [
        ngrams(words(normalize(question)), _QUESTION_NGRAM_SIZE) for question in _questions(t1)
    ]
    findings: list[Finding] = []
    for question in _questions(draft):
        grams = ngrams(words(normalize(question)), _QUESTION_NGRAM_SIZE)
        for t1_grams in t1_question_grams:
            similarity = jaccard(grams, t1_grams)
            if similarity >= threshold:
                findings.append(
                    Finding(
                        rule_id="followup_advances",
                        severity=Severity.WARNING,
                        message=(
                            f"re-asks T1's question in reworded form "
                            f"(similarity {similarity:.2f}): {question!r}"
                        ),
                        draft_id=draft.id,
                    )
                )
                break
    return findings
