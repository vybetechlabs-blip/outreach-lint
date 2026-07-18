"""Command-line interface.

``outreach-lint PATH`` lints one draft file or a directory/batch of drafts,
prints a colorized severity-grouped report (or ``--json``), and exits non-zero
under ``--fail-under`` so it can gate CI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from outreach_lint import __version__, llm
from outreach_lint.config import ConfigError, load_config
from outreach_lint.linter import lint_batch
from outreach_lint.loader import LoaderError, load_path
from outreach_lint.models import BatchReport, Finding, LintReport, Severity

app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

_SEVERITY_ORDER = [Severity.ERROR, Severity.WARNING, Severity.INFO]
_SEVERITY_STYLE = {
    Severity.ERROR: "bold red",
    Severity.WARNING: "yellow",
    Severity.INFO: "cyan",
}


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"outreach-lint {__version__}")
        raise typer.Exit()


@app.command()
def lint(
    path: Annotated[
        Path,
        typer.Argument(
            help="A draft file (.md/.txt/.json/.jsonl) or a directory of drafts.",
            show_default=False,
        ),
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the batch report as JSON instead of text.")
    ] = False,
    fail_under: Annotated[
        float | None,
        typer.Option(
            "--fail-under",
            help="Exit non-zero if any draft scores below this (for CI).",
            show_default="off",
        ),
    ] = None,
    use_llm: Annotated[
        bool,
        typer.Option(
            "--llm",
            help="Also run the optional LLM voice check (needs ANTHROPIC_API_KEY; "
            "skipped with a notice when absent).",
        ),
    ] = False,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="User TOML merged over the shipped defaults."),
    ] = None,
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_version_callback, is_eager=True),
    ] = None,
) -> None:
    """Score cold-email drafts against the configured outreach quality rules."""
    error_console = Console(stderr=True)
    try:
        config = load_config(config_path)
        drafts = load_path(path)
    except (ConfigError, LoaderError) as exc:
        error_console.print(f"[bold red]error:[/] {exc}")
        raise typer.Exit(2) from exc

    extra_findings: list[Finding] = []
    if use_llm:
        if not llm.is_available():
            error_console.print(f"[yellow]{llm.SKIP_NOTICE}[/]")
        else:
            for draft in drafts:
                try:
                    extra_findings.extend(llm.run_voice_check(draft, config))
                except Exception as exc:  # API failures must not kill the lint run
                    error_console.print(
                        f"[yellow]voice check failed for '{draft.id}' "
                        f"({type(exc).__name__}); continuing without it[/]"
                    )

    batch = lint_batch(drafts, config, extra_findings=extra_findings)

    if json_output:
        typer.echo(batch.model_dump_json(indent=2))
    else:
        _print_report(batch)

    if fail_under is not None:
        failing = [report for report in batch.reports if report.score < fail_under]
        if failing:
            if not json_output:
                Console().print(
                    f"\n[bold red]FAIL[/] {len(failing)} draft(s) below --fail-under {fail_under:g}"
                )
            raise typer.Exit(1)


def _print_report(batch: BatchReport) -> None:
    console = Console()
    for report in batch.reports:
        _print_draft(console, report)
    if batch.draft_count > 1:
        console.print(
            f"[bold]batch:[/] {batch.draft_count} drafts | "
            f"mean score {batch.mean_score:g} | {batch.total_findings} findings"
        )


def _print_draft(console: Console, report: LintReport) -> None:
    source = f"  [dim]{report.source}[/]" if report.source else ""
    style = "green" if report.score >= 80 else "yellow" if report.score >= 50 else "red"
    console.print(f"[bold]{report.draft_id}[/] — [{style}]{report.score}/100[/]{source}")
    if not report.findings:
        console.print("  [green]no findings[/]\n")
        return
    for severity in _SEVERITY_ORDER:
        for finding in report.findings:
            if finding.severity is not severity:
                continue
            location = f" [dim](line {finding.span.line})[/]" if finding.span else ""
            console.print(
                f"  [{_SEVERITY_STYLE[severity]}]{severity.value:<7}[/] "
                f"[bold]{finding.rule_id}[/]: {finding.message}{location}"
            )
    console.print()
