"""Optional LLM voice check — one API call per draft, strictly opt-in.

Hard rules:

* Runs only when the caller passes ``--llm`` AND ``ANTHROPIC_API_KEY`` is set
  in the environment. Missing key → clean skip with a notice, never a failure.
* The key is read from the environment at call time, never logged, never
  persisted.
* Model output is parsed defensively: code fences stripped, the outermost JSON
  object extracted, and malformed output degrades to a single ``info`` finding
  instead of crashing the run.

The model rates four voice dimensions (1-5, higher is better):

* ``peer_to_peer``      — peer-to-peer vs vendor-to-prospect
* ``curiosity``         — opens a conversation vs prescribes a diagnosis
* ``naturalness``       — natural voice vs over-polished / machine-generated
* ``grounding``         — specific claims are category patterns, never invented
  facts about this recipient's internal operations

Any sentence asserting an internal fact about the prospect the sender could
not actually know is returned in ``ungrounded_claims`` and flagged as a
warning — grounding integrity is the one dimension treated as more than tone.
"""

from __future__ import annotations

import json
import os
import re

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from outreach_lint.models import Config, Draft, Finding, Severity

API_KEY_ENV = "ANTHROPIC_API_KEY"
SKIP_NOTICE = (
    f"voice check skipped: {API_KEY_ENV} not set. All deterministic rules ran; "
    "the linter is fully functional without the LLM check."
)

_LOW_SCORE_THRESHOLD = 2

_PROMPT_TEMPLATE = """\
You are reviewing a cold-email draft for voice quality. Rate each dimension
from 1 (bad) to 5 (good) and list any ungrounded claims.

Dimensions:
- peer_to_peer: 5 = reads peer-to-peer, 1 = reads vendor-to-prospect.
- curiosity: 5 = opens a conversation, 1 = prescribes a diagnosis.
- naturalness: 5 = natural human voice, 1 = over-polished / machine-generated.
- grounding: 5 = specific claims are category patterns ("something I've seen
  across service businesses"), 1 = asserts specific internal facts about this
  recipient's operations that the sender could not actually know.

Also return ungrounded_claims: every sentence (verbatim) that asserts a
specific internal fact about the recipient the sender could not know.
Return an empty list if there are none.

Respond with JSON only, no prose, exactly this shape:
{{"peer_to_peer": {{"score": 1, "note": "..."}},
  "curiosity": {{"score": 1, "note": "..."}},
  "naturalness": {{"score": 1, "note": "..."}},
  "grounding": {{"score": 1, "note": "..."}},
  "ungrounded_claims": ["..."]}}

Draft:
---
{body}
---
"""


class VoiceRating(BaseModel):
    model_config = ConfigDict(extra="ignore")

    score: int = Field(ge=1, le=5)
    note: str = ""


class VoiceCheckResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    peer_to_peer: VoiceRating
    curiosity: VoiceRating
    naturalness: VoiceRating
    grounding: VoiceRating
    ungrounded_claims: list[str] = Field(default_factory=list)


def is_available() -> bool:
    return bool(os.environ.get(API_KEY_ENV))


def parse_voice_json(text: str) -> VoiceCheckResult:
    """Parse model output defensively: strip code fences, take the outermost
    JSON object, validate. Raises ``ValueError`` on anything unusable."""
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON in model output: {exc}") from exc
    try:
        return VoiceCheckResult.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"model output did not match the expected shape: {exc}") from exc


def _call_model(prompt: str, config: Config) -> str:
    """Single Messages API call. Isolated so tests can monkeypatch it; never
    called without an API key present."""
    import anthropic

    cfg = config.rules.voice_check
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    response = client.messages.create(
        model=cfg.model,
        max_tokens=cfg.max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if hasattr(block, "text"))


def result_to_findings(result: VoiceCheckResult, draft_id: str) -> list[Finding]:
    findings: list[Finding] = []
    dimensions = {
        "peer_to_peer": result.peer_to_peer,
        "curiosity": result.curiosity,
        "naturalness": result.naturalness,
        "grounding": result.grounding,
    }
    for name, rating in dimensions.items():
        if rating.score <= _LOW_SCORE_THRESHOLD:
            note = f" — {rating.note}" if rating.note else ""
            findings.append(
                Finding(
                    rule_id="voice_check",
                    severity=Severity.WARNING,
                    message=f"voice: {name} scored {rating.score}/5{note}",
                    draft_id=draft_id,
                )
            )
    for claim in result.ungrounded_claims:
        findings.append(
            Finding(
                rule_id="voice_check",
                severity=Severity.WARNING,
                message=f"ungrounded claim about the recipient: {claim!r}",
                draft_id=draft_id,
            )
        )
    return findings


def run_voice_check(draft: Draft, config: Config) -> list[Finding]:
    """Voice-check one draft. Returns findings; malformed model output degrades
    to a single info finding. Callers must gate on :func:`is_available`."""
    text = _call_model(_PROMPT_TEMPLATE.format(body=draft.body), config)
    try:
        result = parse_voice_json(text)
    except ValueError as exc:
        return [
            Finding(
                rule_id="voice_check",
                severity=Severity.INFO,
                message=f"voice check returned unusable output ({exc}); ignored",
                draft_id=draft.id,
            )
        ]
    return result_to_findings(result, draft.id)
