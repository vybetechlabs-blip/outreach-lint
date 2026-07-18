"""Orchestrator: run every enabled rule over the drafts and build reports.

Scoring: each draft starts at 100; every finding deducts its severity's weight
from ``[scoring]`` (or the rule's own ``weight`` override), and the result
clamps to 0. Batch-rule findings count against the draft they attach to.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from outreach_lint.models import BatchReport, Config, Draft, Finding, LintReport
from outreach_lint.rules import BatchRuleFn, DraftRuleFn, all_rules


def run_rules(drafts: Sequence[Draft], config: Config) -> list[Finding]:
    """Every finding from every enabled registered rule, in rule order."""
    findings: list[Finding] = []
    for spec in all_rules():
        if not config.rule_config(spec.rule_id).enabled:
            continue
        if spec.scope == "draft":
            draft_fn = cast(DraftRuleFn, spec.fn)
            for draft in drafts:
                findings.extend(draft_fn(draft, config))
        else:
            batch_fn = cast(BatchRuleFn, spec.fn)
            findings.extend(batch_fn(drafts, config))
    return findings


def score_draft(findings: Sequence[Finding], config: Config) -> int:
    total = 100.0
    for finding in findings:
        rule_weight = config.rule_config(finding.rule_id).weight
        total -= config.deduction(finding.severity, rule_weight)
    return max(0, round(total))


def lint_batch(
    drafts: Sequence[Draft],
    config: Config,
    extra_findings: Sequence[Finding] = (),
) -> BatchReport:
    """Lint a batch. ``extra_findings`` lets callers (the optional LLM voice
    check) contribute findings that score like any rule's."""
    findings = run_rules(drafts, config) + list(extra_findings)
    by_draft: dict[str, list[Finding]] = {draft.id: [] for draft in drafts}
    for finding in findings:
        by_draft.setdefault(finding.draft_id, []).append(finding)
    reports = [
        LintReport(
            draft_id=draft.id,
            source=draft.source,
            score=score_draft(by_draft[draft.id], config),
            findings=by_draft[draft.id],
        )
        for draft in drafts
    ]
    total_findings = sum(len(report.findings) for report in reports)
    mean = sum(report.score for report in reports) / len(reports) if reports else 0.0
    return BatchReport(
        reports=reports,
        draft_count=len(reports),
        mean_score=round(mean, 1),
        total_findings=total_findings,
    )


def lint_one(draft: Draft, config: Config) -> LintReport:
    """Lint a single draft (batch rules see a batch of one)."""
    return lint_batch([draft], config).reports[0]
