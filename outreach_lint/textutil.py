"""Small, dependency-free text helpers shared by the rules.

Everything here is pure and deterministic. The readability functions implement
Flesch reading ease / Flesch-Kincaid grade directly (with a standard
vowel-group syllable heuristic) rather than pulling in a dependency; the
heuristic is approximate for loanwords but stable, which matters more for a
linter than dictionary-perfect syllable counts.
"""

from __future__ import annotations

import re
from typing import NamedTuple

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])[\)\"']*\s+")
_NORMALIZE_STRIP_RE = re.compile(r"[^a-z0-9\s]+")


class Sentence(NamedTuple):
    """A sentence plus its character offsets within the source body."""

    text: str
    start: int
    end: int


def line_of(offset: int, body: str) -> int:
    """1-based line number of a character offset."""
    return body.count("\n", 0, offset) + 1


def words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def word_count(text: str) -> int:
    return len(words(text))


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for comparing phrasings."""
    lowered = _NORMALIZE_STRIP_RE.sub(" ", text.lower())
    return " ".join(lowered.split())


def sentences(body: str) -> list[Sentence]:
    """Split a body into sentences, preserving offsets.

    Splitting is intentionally simple (terminal punctuation + whitespace);
    cold emails are short prose, not legal text.
    """
    result: list[Sentence] = []
    cursor = 0
    for match in _SENTENCE_END_RE.finditer(body):
        chunk = body[cursor : match.start() + 1]
        if chunk.strip():
            result.append(_trimmed(chunk, cursor))
        cursor = match.end()
    tail = body[cursor:]
    if tail.strip():
        result.append(_trimmed(tail, cursor))
    return result


def _trimmed(chunk: str, base: int) -> Sentence:
    stripped = chunk.strip()
    start = base + chunk.index(stripped[0])
    return Sentence(stripped, start, start + len(stripped))


def ngrams(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    """Token n-grams as a set; falls back to unigrams when fewer than n tokens."""
    if len(tokens) < n:
        return {(token,) for token in tokens}
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def jaccard(a: set[tuple[str, ...]], b: set[tuple[str, ...]]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def phrase_spans(body: str, phrase: str) -> list[tuple[int, int]]:
    """Whole-phrase, case-insensitive occurrences of ``phrase`` in ``body``.

    Boundaries are non-word lookarounds rather than ``\\b`` so phrases that end
    in symbols (e.g. ``100%``) still match as whole phrases.
    """
    pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", re.IGNORECASE)
    return [match.span() for match in pattern.finditer(body)]


# ---------------------------------------------------------------------------
# Readability
# ---------------------------------------------------------------------------

_VOWEL_GROUP_RE = re.compile(r"[aeiouy]+")


def syllable_count(word: str) -> int:
    """Approximate syllables: vowel groups, minus a common silent trailing 'e'."""
    lowered = re.sub(r"[^a-z]", "", word.lower())
    if not lowered:
        return 0
    count = len(_VOWEL_GROUP_RE.findall(lowered))
    if lowered.endswith("e") and not lowered.endswith(("le", "ee")) and count > 1:
        count -= 1
    return max(count, 1)


def _readability_inputs(text: str) -> tuple[int, int, int]:
    ws = words(text)
    sentence_count = max(len(sentences(text)), 1)
    syllables = sum(syllable_count(word) for word in ws)
    return len(ws), sentence_count, syllables


def flesch_reading_ease(text: str) -> float:
    """Flesch reading ease: higher is easier; ~60-80 is conversational."""
    n_words, n_sentences, n_syllables = _readability_inputs(text)
    if n_words == 0:
        return 100.0
    return 206.835 - 1.015 * (n_words / n_sentences) - 84.6 * (n_syllables / n_words)


def flesch_kincaid_grade(text: str) -> float:
    """US school-grade estimate of the text's complexity."""
    n_words, n_sentences, n_syllables = _readability_inputs(text)
    if n_words == 0:
        return 0.0
    return 0.39 * (n_words / n_sentences) + 11.8 * (n_syllables / n_words) - 15.59
