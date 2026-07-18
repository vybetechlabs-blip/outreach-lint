"""Per-draft rules: each takes one draft plus the merged config and returns findings.

Every rule here is pure — no IO, no state — so each is trivially unit-testable
and safe to run in any order.
"""

from __future__ import annotations

import re

from outreach_lint.models import Config, Draft, Finding, Severity, Span
from outreach_lint.rules import rule
from outreach_lint.textutil import (
    flesch_kincaid_grade,
    flesch_reading_ease,
    line_of,
    phrase_spans,
    sentences,
    word_count,
)

AUTOMATION_RE = re.compile(r"\bautomat(?:e|es|ed|ing|ion|ions)\b", re.IGNORECASE)

_QUOTED_PHRASE_RE = re.compile(r"\"[^\"]+\s[^\"]+\"|“[^”]+\s[^”]+”")
_NUMBERISH_RE = re.compile(r"\b\d[\d,.]*\b")
_URL_RE = re.compile(r"https?://\S+|\bwww\.\S+", re.IGNORECASE)
_MIDSENTENCE_PROPER_RE = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")


def _span(draft: Draft, start: int, end: int) -> Span:
    return Span(start=start, end=end, line=line_of(start, draft.body))


@rule("spam_phrases", scope="draft")
def spam_phrases(draft: Draft, config: Config) -> list[Finding]:
    """Flag configured spam-trigger phrases and excessive exclamation marks."""
    cfg = config.rules.spam_phrases
    findings: list[Finding] = []
    for phrase in cfg.phrases:
        for start, end in phrase_spans(draft.body, phrase):
            findings.append(
                Finding(
                    rule_id="spam_phrases",
                    severity=Severity.WARNING,
                    message=f'spam-trigger phrase "{phrase}"',
                    draft_id=draft.id,
                    span=_span(draft, start, end),
                )
            )
    exclamations = draft.body.count("!")
    if exclamations > cfg.max_exclamations:
        first = draft.body.index("!")
        findings.append(
            Finding(
                rule_id="spam_phrases",
                severity=Severity.WARNING,
                message=f"{exclamations} exclamation marks (max {cfg.max_exclamations})",
                draft_id=draft.id,
                span=_span(draft, first, first + 1),
            )
        )
    return findings


@rule("unfilled_tokens", scope="draft")
def unfilled_tokens(draft: Draft, config: Config) -> list[Finding]:
    """Detect leftover merge placeholders like ``{{company}}`` — always an error."""
    matches: list[tuple[int, int, str]] = []
    for pattern in config.rules.unfilled_tokens.patterns:
        matches.extend(
            (match.start(), match.end(), match.group(0))
            for match in re.finditer(pattern, draft.body)
        )
    # Widest match first, so `{first_name}` inside `{{first_name}}` reports once.
    matches.sort(key=lambda m: (m[0], -(m[1] - m[0])))
    findings: list[Finding] = []
    covered_end = -1
    for start, end, token in matches:
        if end <= covered_end:
            continue
        covered_end = end
        findings.append(
            Finding(
                rule_id="unfilled_tokens",
                severity=Severity.ERROR,
                message=f"unfilled merge token {token!r}",
                draft_id=draft.id,
                span=_span(draft, start, end),
            )
        )
    return findings


@rule("personalization_present", scope="draft")
def personalization_present(draft: Draft, config: Config) -> list[Finding]:
    """Require a personalization anchor: a populated ``hook`` field, or a
    detectable specific reference in the body (quoted phrase, number, URL, or a
    mid-sentence proper noun). Heuristic by nature — absence is a warning."""
    if draft.hook and draft.hook.strip():
        return []
    body = draft.body
    has_anchor = bool(
        _QUOTED_PHRASE_RE.search(body)
        or _NUMBERISH_RE.search(body)
        or _URL_RE.search(body)
        or _MIDSENTENCE_PROPER_RE.search(body)
    )
    if has_anchor:
        return []
    return [
        Finding(
            rule_id="personalization_present",
            severity=Severity.WARNING,
            message="no personalization anchor: hook field empty and no specific reference found",
            draft_id=draft.id,
        )
    ]


@rule("length_band", scope="draft")
def length_band(draft: Draft, config: Config) -> list[Finding]:
    """Word count must sit inside the configured band; cold emails run short."""
    cfg = config.rules.length_band
    count = word_count(draft.body)
    if count < cfg.min_words:
        message = f"too short: {count} words (band {cfg.min_words}-{cfg.max_words})"
    elif count > cfg.max_words:
        message = f"too long: {count} words (band {cfg.min_words}-{cfg.max_words})"
    else:
        return []
    return [
        Finding(
            rule_id="length_band",
            severity=Severity.WARNING,
            message=message,
            draft_id=draft.id,
        )
    ]


@rule("reading_level", scope="draft")
def reading_level(draft: Draft, config: Config) -> list[Finding]:
    """Flag drafts that read too complex or too polished.

    Both signals point the same direction: dense, over-worked prose reads
    machine-generated. Grade above the ceiling and reading ease below the floor
    are reported separately so the report says which threshold tripped.
    """
    cfg = config.rules.reading_level
    if word_count(draft.body) == 0:
        return []
    findings: list[Finding] = []
    grade = flesch_kincaid_grade(draft.body)
    ease = flesch_reading_ease(draft.body)
    if grade > cfg.max_grade:
        findings.append(
            Finding(
                rule_id="reading_level",
                severity=Severity.WARNING,
                message=f"grade level {grade:.1f} exceeds ceiling {cfg.max_grade:.1f}",
                draft_id=draft.id,
            )
        )
    if ease < cfg.min_reading_ease:
        findings.append(
            Finding(
                rule_id="reading_level",
                severity=Severity.WARNING,
                message=(
                    f"reading ease {ease:.0f} below floor {cfg.min_reading_ease:.0f} "
                    "(over-polished / over-complex)"
                ),
                draft_id=draft.id,
            )
        )
    return findings


@rule("hedge_count", scope="draft")
def hedge_count(draft: Draft, config: Config) -> list[Finding]:
    """At most one hedge per draft; a second reads unsure of the whole premise."""
    cfg = config.rules.hedge_count
    hits: list[tuple[str, int, int]] = []
    for hedge in cfg.lexicon:
        hits.extend((hedge, start, end) for start, end in phrase_spans(draft.body, hedge))
    if len(hits) <= cfg.max_hedges:
        return []
    hits.sort(key=lambda hit: hit[1])
    listed = ", ".join(f'"{hedge}"' for hedge, _, _ in hits)
    overflow_start, overflow_end = hits[cfg.max_hedges][1], hits[cfg.max_hedges][2]
    return [
        Finding(
            rule_id="hedge_count",
            severity=Severity.WARNING,
            message=f"{len(hits)} hedges (max {cfg.max_hedges}): {listed}",
            draft_id=draft.id,
            span=_span(draft, overflow_start, overflow_end),
        )
    ]


@rule("banned_constructions", scope="draft")
def banned_constructions(draft: Draft, config: Config) -> list[Finding]:
    """Flag configured regexes for phrasings the author knows they template."""
    findings: list[Finding] = []
    for pattern in config.rules.banned_constructions.patterns:
        for match in re.finditer(pattern, draft.body, re.IGNORECASE):
            findings.append(
                Finding(
                    rule_id="banned_constructions",
                    severity=Severity.WARNING,
                    message=f"banned construction {match.group(0)!r} (pattern {pattern!r})",
                    draft_id=draft.id,
                    span=_span(draft, match.start(), match.end()),
                )
            )
    return findings


@rule("t1_no_pitch", scope="draft")
def t1_no_pitch(draft: Draft, config: Config) -> list[Finding]:
    """A first touch opens a conversation; it does not pitch.

    On ``touch == T1``, flag pitch/CTA/pricing phrases and any use of
    automate/automating/automation.
    """
    if draft.touch != "T1":
        return []
    cfg = config.rules.t1_no_pitch
    findings: list[Finding] = []
    for phrase in cfg.pitch_phrases:
        for start, end in phrase_spans(draft.body, phrase):
            findings.append(
                Finding(
                    rule_id="t1_no_pitch",
                    severity=Severity.ERROR,
                    message=f'pitch language on a first touch: "{phrase}"',
                    draft_id=draft.id,
                    span=_span(draft, start, end),
                )
            )
    for match in AUTOMATION_RE.finditer(draft.body):
        findings.append(
            Finding(
                rule_id="t1_no_pitch",
                severity=Severity.ERROR,
                message=f"{match.group(0)!r} on a first touch",
                draft_id=draft.id,
                span=_span(draft, match.start(), match.end()),
            )
        )
    return findings


@rule("banned_in_opener_closer", scope="draft")
def banned_in_opener_closer(draft: Draft, config: Config) -> list[Finding]:
    """The opener (first sentence) and closer (last sentence) must not lead with
    automation language; those slots carry the most weight."""
    del config  # no options beyond enabled/weight
    sents = sentences(draft.body)
    if not sents:
        return []
    findings: list[Finding] = []
    positions = [("opener", sents[0])]
    if len(sents) > 1:
        positions.append(("closer", sents[-1]))
    for position, sentence in positions:
        match = AUTOMATION_RE.search(sentence.text)
        if match:
            start = sentence.start + match.start()
            findings.append(
                Finding(
                    rule_id="banned_in_opener_closer",
                    severity=Severity.WARNING,
                    message=f"{match.group(0)!r} in the {position}",
                    draft_id=draft.id,
                    span=_span(draft, start, start + len(match.group(0))),
                )
            )
    return findings
