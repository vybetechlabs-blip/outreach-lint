"""Core data models: drafts, findings, reports, and the validated config tree.

Everything the linter passes between modules is a Pydantic model, so shape
errors surface at the boundary (loading drafts, loading config) rather than
deep inside a rule.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Touch = Literal["T1", "T2", "T3", "T4"]

TOUCH_ORDER: dict[str, int] = {"T1": 1, "T2": 2, "T3": 3, "T4": 4}


class Severity(StrEnum):
    """Severity of a finding; drives the score deduction weight."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Span(BaseModel):
    """Character span of a finding within a draft body (0-based, end-exclusive)."""

    model_config = ConfigDict(frozen=True)

    start: int
    end: int
    line: int
    """1-based line number of ``start`` within the body."""


class Draft(BaseModel):
    """A single cold-email draft plus optional sequence metadata."""

    model_config = ConfigDict(frozen=True)

    id: str
    body: str
    touch: Touch | None = None
    sequence_id: str | None = None
    hook: str | None = None
    """The specific personalization anchor this draft is built on."""
    source: str | None = None
    """File the draft was loaded from, for report display."""


class Finding(BaseModel):
    """One rule violation (or note) attached to a draft."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    severity: Severity
    message: str
    draft_id: str
    span: Span | None = None


class LintReport(BaseModel):
    """Per-draft result: 0-100 score plus every finding that hit the draft."""

    draft_id: str
    source: str | None = None
    score: int
    findings: list[Finding]


class BatchReport(BaseModel):
    """Batch-level result aggregating every draft's report."""

    reports: list[LintReport]
    draft_count: int
    mean_score: float
    total_findings: int


# ---------------------------------------------------------------------------
# Config models
#
# ``extra="forbid"`` everywhere so a typo'd key in a user TOML fails loudly
# instead of silently doing nothing.
# ---------------------------------------------------------------------------


class ScoringConfig(BaseModel):
    """Points deducted per finding, by severity. Score starts at 100, clamps at 0."""

    model_config = ConfigDict(extra="forbid")

    error: float = 25.0
    warning: float = 10.0
    info: float = 3.0

    def weight(self, severity: Severity) -> float:
        return {
            Severity.ERROR: self.error,
            Severity.WARNING: self.warning,
            Severity.INFO: self.info,
        }[severity]


class RuleConfig(BaseModel):
    """Options every rule shares."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    weight: float | None = None
    """If set, overrides the severity weight for this rule's findings."""


def _validate_patterns(patterns: list[str]) -> list[str]:
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"invalid regex {pattern!r}: {exc}") from exc
    return patterns


class SpamPhrasesConfig(RuleConfig):
    phrases: list[str] = Field(
        default_factory=lambda: [
            "free",
            "guarantee",
            "act now",
            "limited time",
            "click here",
            "risk-free",
            "100%",
        ]
    )
    max_exclamations: int = 1


class UnfilledTokensConfig(RuleConfig):
    patterns: list[str] = Field(
        default_factory=lambda: [
            r"\{\{[^{}]*\}\}",
            r"\{[A-Za-z_][A-Za-z0-9_]*\}",
            r"\[\[[^\[\]]*\]\]",
            r"%[A-Z][A-Z0-9_]*%",
            r"<<[^<>]*>>",
        ]
    )

    _check_patterns = field_validator("patterns")(_validate_patterns)


class PersonalizationConfig(RuleConfig):
    pass


class LengthBandConfig(RuleConfig):
    min_words: int = 40
    max_words: int = 120


class ReadingLevelConfig(RuleConfig):
    max_grade: float = 9.0
    min_reading_ease: float = 50.0


class HedgeCountConfig(RuleConfig):
    lexicon: list[str] = Field(
        default_factory=lambda: [
            "maybe",
            "perhaps",
            "i could be wrong",
            "my guess",
            "i imagine",
            "possibly",
        ]
    )
    max_hedges: int = 1


class BannedConstructionsConfig(RuleConfig):
    patterns: list[str] = Field(
        default_factory=lambda: [
            r"\bbefore\b[^.!?]{0,60}\bbecomes the constraint\b",
        ]
    )

    _check_patterns = field_validator("patterns")(_validate_patterns)


class T1NoPitchConfig(RuleConfig):
    pitch_phrases: list[str] = Field(
        default_factory=lambda: [
            "book a call",
            "schedule a demo",
            "hop on a call",
            "15 minutes",
            "pricing",
            "our platform",
            "our product",
            "we offer",
            "free trial",
            "sign up",
        ]
    )


class BannedInOpenerCloserConfig(RuleConfig):
    pass


class OpenerVarietyConfig(RuleConfig):
    ngram_size: int = 3
    similarity_threshold: float = 0.6


class CloserRoundRobinConfig(RuleConfig):
    window: int = 3
    """A closer may not repeat until ``window - 1`` other closers have run."""


class SequenceNoReuseConfig(RuleConfig):
    pass


class AntiFormulaConfig(RuleConfig):
    prefix_words: int = 30
    # Bigrams at a lower threshold: shared skeletons survive noun swaps, which
    # is exactly how templated batches differ.
    ngram_size: int = 2
    similarity_threshold: float = 0.4
    min_cluster_size: int = 3


class FollowupAdvancesConfig(RuleConfig):
    pitch_phrases: list[str] = Field(
        default_factory=lambda: [
            "book a call",
            "schedule a demo",
            "hop on a call",
            "pricing",
            "free trial",
            "sign up",
        ]
    )
    escalation_cues: list[str] = Field(
        default_factory=lambda: [
            "clearly you",
            "obviously you",
            "i know you",
            "no doubt you",
            "you definitely",
            "your team must",
        ]
    )
    question_similarity_threshold: float = 0.6


class VoiceCheckConfig(RuleConfig):
    """Optional LLM voice check; only runs with --llm and an API key present."""

    enabled: bool = True
    model: str = "claude-sonnet-5"
    max_tokens: int = 1024


class RulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spam_phrases: SpamPhrasesConfig = Field(default_factory=SpamPhrasesConfig)
    unfilled_tokens: UnfilledTokensConfig = Field(default_factory=UnfilledTokensConfig)
    personalization_present: PersonalizationConfig = Field(default_factory=PersonalizationConfig)
    length_band: LengthBandConfig = Field(default_factory=LengthBandConfig)
    reading_level: ReadingLevelConfig = Field(default_factory=ReadingLevelConfig)
    hedge_count: HedgeCountConfig = Field(default_factory=HedgeCountConfig)
    banned_constructions: BannedConstructionsConfig = Field(
        default_factory=BannedConstructionsConfig
    )
    t1_no_pitch: T1NoPitchConfig = Field(default_factory=T1NoPitchConfig)
    banned_in_opener_closer: BannedInOpenerCloserConfig = Field(
        default_factory=BannedInOpenerCloserConfig
    )
    opener_variety: OpenerVarietyConfig = Field(default_factory=OpenerVarietyConfig)
    closer_round_robin: CloserRoundRobinConfig = Field(default_factory=CloserRoundRobinConfig)
    sequence_no_reuse: SequenceNoReuseConfig = Field(default_factory=SequenceNoReuseConfig)
    anti_formula: AntiFormulaConfig = Field(default_factory=AntiFormulaConfig)
    followup_advances: FollowupAdvancesConfig = Field(default_factory=FollowupAdvancesConfig)
    voice_check: VoiceCheckConfig = Field(default_factory=VoiceCheckConfig)


class Config(BaseModel):
    """Fully merged + validated linter configuration."""

    model_config = ConfigDict(extra="forbid")

    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)

    def rule_config(self, rule_id: str) -> RuleConfig:
        cfg = getattr(self.rules, rule_id, None)
        if not isinstance(cfg, RuleConfig):
            raise KeyError(f"unknown rule id: {rule_id}")
        return cfg

    def deduction(self, finding_severity: Severity, rule_weight: float | None) -> float:
        return rule_weight if rule_weight is not None else self.scoring.weight(finding_severity)
