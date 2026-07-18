"""Shared synthetic fixtures. Every name, company, and email body in the test
suite is invented."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from outreach_lint.models import Config, Draft, Touch

# A clean, well-formed first touch: inside the length band, simple language,
# one question, no pitch, no spam, no leftover tokens.
CLEAN_BODY = (
    "Hi Mara,\n"
    "\n"
    "Saw your June post about doubling the shop floor — that pace is rare in "
    "custom cabinetry.\n"
    "\n"
    "Most shops I talk to hit a wall right after a jump like that: quotes go "
    "out slower just when lead flow picks up.\n"
    "\n"
    "Curious how quoting is holding up on your end?\n"
    "\n"
    "No agenda — happy to swap notes either way.\n"
    "\n"
    "Alex"
)

DraftFactory = Callable[..., Draft]


@pytest.fixture(autouse=True)
def _plain_console_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep console output plain under any environment.

    Rich force-enables ANSI styling when it detects a CI provider (e.g. the
    GITHUB_ACTIONS env var), even for non-tty streams like CliRunner's capture
    buffer — which breaks substring assertions on CLI output. Strip the CI
    markers and set NO_COLOR so test output is identical locally and in CI.
    """
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "dumb")


@pytest.fixture
def config() -> Config:
    return Config()


@pytest.fixture
def make_draft() -> DraftFactory:
    def _make(
        body: str = CLEAN_BODY,
        id: str = "draft-1",
        touch: Touch | None = None,
        sequence_id: str | None = None,
        hook: str | None = "their June post about doubling the shop floor",
    ) -> Draft:
        return Draft(id=id, body=body, touch=touch, sequence_id=sequence_id, hook=hook)

    return _make
