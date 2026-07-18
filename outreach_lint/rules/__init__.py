"""Rule registry.

Rules self-register via the :func:`rule` decorator, so the orchestrator, the
config tree, and the CLI never import individual rules by name — adding a rule
is one function in the right module plus one config model.

Two scopes exist:

* ``draft`` — ``fn(draft, config) -> list[Finding]``, called once per draft.
* ``batch`` — ``fn(drafts, config) -> list[Finding]``, called once with every
  draft; findings attach to specific drafts via ``Finding.draft_id``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from outreach_lint.models import Config, Draft, Finding

DraftRuleFn = Callable[[Draft, Config], list[Finding]]
BatchRuleFn = Callable[[Sequence[Draft], Config], list[Finding]]
RuleFn = DraftRuleFn | BatchRuleFn

Scope = Literal["draft", "batch"]


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    scope: Scope
    fn: RuleFn


_REGISTRY: dict[str, RuleSpec] = {}


def rule(rule_id: str, scope: Scope) -> Callable[[RuleFn], RuleFn]:
    """Register a rule function under ``rule_id``."""

    def decorator(fn: RuleFn) -> RuleFn:
        if rule_id in _REGISTRY:
            raise ValueError(f"duplicate rule id: {rule_id}")
        _REGISTRY[rule_id] = RuleSpec(rule_id=rule_id, scope=scope, fn=fn)
        return fn

    return decorator


def all_rules() -> list[RuleSpec]:
    """Every registered rule, in registration order."""
    return list(_REGISTRY.values())


def get_rule(rule_id: str) -> RuleSpec:
    return _REGISTRY[rule_id]


# Importing the rule modules populates the registry.
from outreach_lint.rules import batch, per_draft  # noqa: E402,F401
