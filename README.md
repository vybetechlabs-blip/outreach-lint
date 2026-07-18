# outreach-lint

**Static analysis for cold-email drafts.** Scores each draft 0–100 against a
configurable set of outreach quality rules — spam triggers, leftover merge
tokens, missing personalization, templated openers, re-pitched follow-ups —
and prints a lint report you can read, pipe as JSON, or gate CI on.

## Why this exists

Cold-outreach batches drift. The first five drafts are hand-written; by draft
forty they share an opener skeleton, the closers repeat, a `{{first_name}}`
slips through, and every follow-up re-asks the first touch's question with the
nouns swapped. Reply rates fall and nobody can say why, because each draft
*looks* fine on its own.

`outreach-lint` quantifies that drift. Per-draft rules catch the mechanical
mistakes; batch rules compare drafts against each other and surface the
templating — repeated opener constructions, closer reuse, shared structural
formulas — that only shows up across the set.

## Install

Python 3.11+.

```bash
git clone <this-repo>
cd outreach-lint
pip install -e .

# for development (tests, lint, type-checking):
pip install -e ".[dev]"
```

This exposes an `outreach-lint` console script:

```bash
outreach-lint --help
```

## Quickstart

```bash
# lint one draft
outreach-lint examples/good_t1.md

# lint a batch (enables the cross-draft rules)
outreach-lint examples/templated_batch.jsonl

# machine-readable output
outreach-lint examples/templated_batch.jsonl --json

# gate CI: exit 1 if any draft scores below 70
outreach-lint drafts/ --fail-under 70
```

### Input formats

Drafts are plain text plus optional metadata: `touch` (`T1`–`T4`),
`sequence_id` (groups one prospect's touches), and `hook` (the specific
personalization anchor the draft is built on).

**Markdown / plaintext** with optional YAML front-matter:

```markdown
---
touch: T1
sequence_id: seq-harborpine
hook: their June post about doubling the shop floor
---
Hi Mara,

Saw your June post about doubling the shop floor...
```

**JSON / JSONL** — one object per draft:

```json
{"id": "tpl-a1", "touch": "T1", "sequence_id": "seq-alpha", "body": "..."}
```

## Worked example

`examples/templated_batch.jsonl` is a deliberately bad batch: six synthetic
drafts written off one skeleton, with a leftover merge token, a pitchy first
touch, and a T2 that re-asks T1's question. Running
`outreach-lint examples/templated_batch.jsonl` produces (abridged):

```text
tpl-a1 — 0/100  examples/templated_batch.jsonl
  error   unfilled_tokens: unfilled merge token '{{first_name}}' (line 1)
  error   t1_no_pitch: pitch language on a first touch: "book a call" (line 1)
  error   t1_no_pitch: pitch language on a first touch: "we offer" (line 1)
  error   t1_no_pitch: pitch language on a first touch: "free trial" (line 1)
  warning anti_formula: shares a structural formula with 3 other draft(s):
          'tpl-a1', 'tpl-b1', 'tpl-b2', 'tpl-c1'
  warning spam_phrases: spam-trigger phrase "free" (line 1)
  warning personalization_present: no personalization anchor: hook field empty
          and no specific reference found

tpl-a2 — 0/100  examples/templated_batch.jsonl
  error   sequence_no_reuse: opener reused within sequence 'seq-alpha' (first used in 'tpl-a1')
  error   sequence_no_reuse: closer reused within sequence 'seq-alpha' (first used in 'tpl-a1')
  warning opener_variety: opener nearly identical to draft 'tpl-a1' (similarity 1.00)
  warning closer_round_robin: closer reused from draft 'tpl-a1' before 2 other closers ran
  warning followup_advances: follow-up re-pitches instead of advancing: "book a call" (line 1)
  warning followup_advances: follow-up escalates assumptions beyond T1: "clearly you" (line 1)
  warning followup_advances: re-asks T1's question in reworded form (similarity 1.00):
          'Open to comparing notes this week?'

tpl-b1 — 50/100  examples/templated_batch.jsonl
  warning opener_variety: opener nearly identical to draft 'tpl-a1' (similarity 0.79)
  ...

batch: 6 drafts | mean score 35 | 36 findings
```

The clean example passes untouched:

```text
$ outreach-lint examples/good_t1.md
good-t1 — 100/100  examples/good_t1.md
  no findings
```

## Rules

Severity weights (configurable): `error` −25, `warning` −10, `info` −3.
Every rule can be disabled (`enabled = false`) or re-weighted (`weight = N`,
overriding the severity weight) under its `[rules.<id>]` table.

### Per-draft rules

| Rule id | Checks | Default severity | Key config |
| --- | --- | --- | --- |
| `spam_phrases` | Spam-trigger phrases ("free", "act now", "risk-free", …) and excessive `!` | warning | `phrases`, `max_exclamations` |
| `unfilled_tokens` | Leftover merge placeholders: `{{company}}`, `{first_name}`, `[[hook]]`, `%CITY%`, `<<plan>>` | **error** | `patterns` (regexes) |
| `personalization_present` | A populated `hook` field, or a detectable specific reference in the body (quoted phrase, number, URL, mid-sentence proper noun) | warning | — |
| `length_band` | Word count inside a target band; cold first-touches run short | warning | `min_words` (40), `max_words` (120) |
| `reading_level` | Flesch-Kincaid grade above a ceiling, or Flesch reading ease below a floor (over-polish reads machine-generated) | warning | `max_grade` (9.0), `min_reading_ease` (50.0) |
| `hedge_count` | More than one hedge ("maybe", "perhaps", "my guess", …) | warning | `lexicon`, `max_hedges` (1) |
| `banned_constructions` | Configurable regexes for phrasings you know you template (seed: "before X becomes the constraint") | warning | `patterns` (regexes) |
| `t1_no_pitch` | On `touch = T1`: pitch/CTA/pricing phrases and any automate/automating/automation | **error** | `pitch_phrases` |
| `banned_in_opener_closer` | automate/automating/automation in the first or last sentence, with the position named | warning | — |

### Batch rules (need ≥2 drafts in one run)

| Rule id | Checks | Default severity | Key config |
| --- | --- | --- | --- |
| `opener_variety` | Near-identical opener constructions across drafts (n-gram overlap on the normalized first sentence); reports the colliding pair | warning | `ngram_size` (3), `similarity_threshold` (0.6) |
| `closer_round_robin` | A closer reused before `window − 1` other closers have run (rolling window over batch order) | warning | `window` (3) |
| `sequence_no_reuse` | Within one `sequence_id`, an opener or closer reused across touches | **error** | — |
| `anti_formula` | Clusters of drafts sharing a structural formula in the opening move (bigram overlap over the first `prefix_words` words); reports the whole cluster | warning | `prefix_words` (30), `ngram_size` (2), `similarity_threshold` (0.4), `min_cluster_size` (3) |

### Follow-up rule

| Rule id | Checks | Default severity | Key config |
| --- | --- | --- | --- |
| `followup_advances` | T2–T4 drafts that re-pitch, escalate assumptions beyond T1, or re-ask T1's question in reworded form (needs T1 in the same run, matched by `sequence_id`) | warning (never error — it's heuristic) | `pitch_phrases`, `escalation_cues`, `question_similarity_threshold` (0.6) |

The heuristics behind `followup_advances` are documented honestly in
[`outreach_lint/rules/followup.py`](outreach_lint/rules/followup.py)'s module
docstring — it flags negative signals it can detect with reasonable precision
and makes no claim to judge what a "genuine insight" is.

## Configuration

The shipped defaults live in
[`outreach_lint/default_config.toml`](outreach_lint/default_config.toml) — that
file is the canonical reference for every knob. Point `--config` at your own
TOML to override any subset; your file is deep-merged over the defaults and the
result is validated. Unknown keys and invalid regexes fail loudly instead of
silently doing nothing.

```toml
# mine.toml — see examples/user_config.example.toml for a fuller version
[scoring]
warning = 15.0                  # make warnings sting more

[rules.length_band]
max_words = 140

[rules.reading_level]
enabled = false                 # turn a rule off

[rules.unfilled_tokens]
weight = 40.0                   # re-weight one rule's findings
```

```bash
outreach-lint drafts/ --config mine.toml
```

Note: list values replace the shipped list (TOML has no "append"), so include
the defaults you want to keep when extending a lexicon.

## Optional LLM voice check

`--llm` adds one model call per draft that rates four voice dimensions —
peer-to-peer vs vendor-to-prospect, curiosity vs diagnosis, over-polish, and
grounding integrity (specific claims must be category patterns, never invented
facts about this recipient's internals). Low scores and ungrounded claims
become ordinary findings that deduct from the score.

* **The tool is fully functional without it.** All 14 core rules are pure
  Python and deterministic.
* Requires `ANTHROPIC_API_KEY` in the environment (see `.env.example`) and the
  `llm` extra: `pip install -e ".[llm]"`. Without a key, `--llm` prints a
  notice and skips — it never fails the run.
* Model output is parsed defensively (code fences stripped, malformed JSON
  degrades to an `info` finding). The key is read from the environment at call
  time and never logged. Tests never make network calls.
* The model is configurable via `[rules.voice_check] model = "..."`.

## Design

* **Rule registry** — rules self-register via a decorator
  (`@rule("spam_phrases", scope="draft")`) into a central registry, so the
  orchestrator, config, and CLI stay decoupled from individual rules. Adding a
  rule is one pure function plus one config model.
* **Pure-function rules** — every rule takes a draft (or the batch) plus the
  merged config and returns `Finding`s. No IO, no state; all IO lives in
  `loader.py`, `cli.py`, and `llm.py`.
* **Pydantic everywhere** — drafts, findings, reports, and the entire config
  tree are Pydantic v2 models with `extra="forbid"`, so a typo'd config key or
  malformed draft record fails at the boundary with a real error message.
* **Scoring** — start at 100, deduct per finding by severity weight (or the
  rule's `weight` override), clamp at 0. Batch-rule findings count against the
  draft they attach to.

```text
outreach_lint/
  models.py              # Draft, Finding, LintReport, BatchReport, Config
  config.py              # defaults + user TOML deep-merge + validation
  default_config.toml    # canonical shipped ruleset
  loader.py              # md front-matter / JSON / JSONL parsing
  textutil.py            # sentences, n-grams, Flesch scoring (dependency-free)
  linter.py              # orchestrator + scoring
  llm.py                 # optional voice check (no-ops without a key)
  cli.py                 # typer CLI
  rules/
    __init__.py          # registry
    per_draft.py         # rules 1-9
    batch.py             # rules 10-13
    followup.py          # rule 14
```

## Development

```bash
make check      # ruff + mypy (strict) + pytest --cov
make fmt        # auto-format
```

On Windows without `make`, run the underlying commands directly:
`ruff check .`, `ruff format --check .`, `mypy outreach_lint`, `pytest`.

CI runs the same gate on Python 3.11 / 3.12 / 3.13.

All example and fixture data is synthetic — invented names, invented
companies. No real prospect data, no PII, and no secrets live anywhere in this
repository or its history.

## License

MIT
