"""Voice-check tests: no network calls anywhere — the API call boundary
(`_call_model`) is monkeypatched with canned strings."""

import json

import pytest
from conftest import DraftFactory

from outreach_lint import llm
from outreach_lint.models import Config, Severity

GOOD_PAYLOAD = {
    "peer_to_peer": {"score": 5, "note": "reads like a peer"},
    "curiosity": {"score": 4, "note": "opens a conversation"},
    "naturalness": {"score": 5, "note": "sounds human"},
    "grounding": {"score": 5, "note": "category patterns only"},
    "ungrounded_claims": [],
}


def test_is_available_requires_env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(llm.API_KEY_ENV, raising=False)
    assert llm.is_available() is False
    monkeypatch.setenv(llm.API_KEY_ENV, "test-key")
    assert llm.is_available() is True


def test_parse_accepts_plain_json() -> None:
    result = llm.parse_voice_json(json.dumps(GOOD_PAYLOAD))
    assert result.peer_to_peer.score == 5
    assert result.ungrounded_claims == []


def test_parse_strips_code_fences_and_prose() -> None:
    fenced = "```json\n" + json.dumps(GOOD_PAYLOAD) + "\n```"
    assert llm.parse_voice_json(fenced).curiosity.score == 4
    chatty = "Here is my assessment:\n" + json.dumps(GOOD_PAYLOAD) + "\nHope that helps!"
    assert llm.parse_voice_json(chatty).naturalness.score == 5


@pytest.mark.parametrize(
    "text",
    [
        "no json here at all",
        "{not: valid json}",
        json.dumps({"peer_to_peer": {"score": 9, "note": "out of range"}}),
        json.dumps({"unexpected": "shape"}),
    ],
)
def test_parse_rejects_unusable_output(text: str) -> None:
    with pytest.raises(ValueError):
        llm.parse_voice_json(text)


def test_low_scores_and_ungrounded_claims_become_warnings() -> None:
    payload = dict(GOOD_PAYLOAD)
    payload["grounding"] = {"score": 1, "note": "asserts internal facts"}
    payload["ungrounded_claims"] = ["Your team spends 12 hours a week on quotes."]
    findings = llm.result_to_findings(llm.parse_voice_json(json.dumps(payload)), "d1")
    assert len(findings) == 2
    assert all(f.severity is Severity.WARNING for f in findings)
    assert any("grounding scored 1/5" in f.message for f in findings)
    assert any("ungrounded claim" in f.message for f in findings)


def test_clean_result_produces_no_findings() -> None:
    result = llm.parse_voice_json(json.dumps(GOOD_PAYLOAD))
    assert llm.result_to_findings(result, "d1") == []


def test_run_voice_check_degrades_on_malformed_output(
    monkeypatch: pytest.MonkeyPatch, make_draft: DraftFactory, config: Config
) -> None:
    monkeypatch.setattr(llm, "_call_model", lambda prompt, cfg: "utter nonsense")
    findings = llm.run_voice_check(make_draft(), config)
    assert len(findings) == 1
    assert findings[0].severity is Severity.INFO
    assert "unusable output" in findings[0].message


def test_run_voice_check_converts_model_output(
    monkeypatch: pytest.MonkeyPatch, make_draft: DraftFactory, config: Config
) -> None:
    payload = dict(GOOD_PAYLOAD)
    payload["peer_to_peer"] = {"score": 2, "note": "reads vendor-to-prospect"}
    monkeypatch.setattr(llm, "_call_model", lambda prompt, cfg: json.dumps(payload))
    findings = llm.run_voice_check(make_draft(), config)
    assert len(findings) == 1
    assert "peer_to_peer scored 2/5" in findings[0].message
