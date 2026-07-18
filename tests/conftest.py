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
