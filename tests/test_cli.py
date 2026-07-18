"""End-to-end CLI tests via typer's CliRunner. No network calls: the --llm
path is exercised only with the key absent (clean skip) or `_call_model`
monkeypatched."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from outreach_lint import llm
from outreach_lint.cli import app

EXAMPLES = Path(__file__).parent.parent / "examples"

runner = CliRunner()


def test_clean_draft_reports_no_findings_and_exits_zero() -> None:
    result = runner.invoke(app, [str(EXAMPLES / "good_t1.md")])
    assert result.exit_code == 0
    assert "good-t1" in result.output
    assert "100/100" in result.output
    assert "no findings" in result.output


def test_templated_batch_report_lists_findings() -> None:
    result = runner.invoke(app, [str(EXAMPLES / "templated_batch.jsonl")])
    assert result.exit_code == 0  # no --fail-under → informational run
    assert "batch:" in result.output
    assert "unfilled_tokens" in result.output
    assert "anti_formula" in result.output


def test_json_output_is_valid_and_structured() -> None:
    result = runner.invoke(app, [str(EXAMPLES / "templated_batch.jsonl"), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["draft_count"] == 6
    assert {report["draft_id"] for report in payload["reports"]} >= {"tpl-a1", "tpl-c2"}
    first = payload["reports"][0]
    assert {"draft_id", "score", "findings"} <= first.keys()


def test_fail_under_gates_the_exit_code() -> None:
    failing = runner.invoke(app, [str(EXAMPLES / "templated_batch.jsonl"), "--fail-under", "60"])
    assert failing.exit_code == 1
    passing = runner.invoke(app, [str(EXAMPLES / "good_t1.md"), "--fail-under", "90"])
    assert passing.exit_code == 0


def test_missing_path_exits_two() -> None:
    result = runner.invoke(app, ["definitely-not-here.md"])
    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_bad_config_exits_two(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("[rules.length_band]\nmax_wordz = 1\n", encoding="utf-8")
    result = runner.invoke(app, [str(EXAMPLES / "good_t1.md"), "--config", str(bad)])
    assert result.exit_code == 2
    assert "max_wordz" in result.output


def test_llm_flag_skips_cleanly_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(llm.API_KEY_ENV, raising=False)
    result = runner.invoke(app, [str(EXAMPLES / "good_t1.md"), "--llm"])
    assert result.exit_code == 0
    assert "voice check skipped" in result.output
    assert "100/100" in result.output


def test_llm_findings_change_the_score(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(llm.API_KEY_ENV, "test-key")
    payload = {
        "peer_to_peer": {"score": 1, "note": "pure vendor voice"},
        "curiosity": {"score": 4, "note": ""},
        "naturalness": {"score": 4, "note": ""},
        "grounding": {"score": 4, "note": ""},
        "ungrounded_claims": [],
    }
    monkeypatch.setattr(llm, "_call_model", lambda prompt, cfg: json.dumps(payload))
    result = runner.invoke(app, [str(EXAMPLES / "good_t1.md"), "--llm"])
    assert result.exit_code == 0
    assert "voice_check" in result.output
    assert "90/100" in result.output


def test_llm_api_failure_does_not_kill_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(llm.API_KEY_ENV, "test-key")

    def _boom(prompt: str, cfg: object) -> str:
        raise RuntimeError("api down")

    monkeypatch.setattr(llm, "_call_model", _boom)
    result = runner.invoke(app, [str(EXAMPLES / "good_t1.md"), "--llm"])
    assert result.exit_code == 0
    assert "voice check failed" in result.output
    assert "100/100" in result.output


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "outreach-lint" in result.output


def test_help_is_complete() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for flag in ("--json", "--fail-under", "--llm", "--config", "--version"):
        assert flag in result.output
