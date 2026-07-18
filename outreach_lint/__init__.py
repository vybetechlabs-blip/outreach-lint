"""outreach-lint: static analysis for cold-email drafts."""

from outreach_lint.models import (
    BatchReport,
    Config,
    Draft,
    Finding,
    LintReport,
    Severity,
    Span,
)

__version__ = "0.1.0"

__all__ = [
    "BatchReport",
    "Config",
    "Draft",
    "Finding",
    "LintReport",
    "Severity",
    "Span",
    "__version__",
]
