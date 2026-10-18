# outreach-lint

[![CI](https://github.com/vybetechlabs-blip/outreach-lint/actions/workflows/ci.yml/badge.svg)](https://github.com/vybetechlabs-blip/outreach-lint/actions/workflows/ci.yml)

**Static analysis for cold-email drafts.** Scores each draft from 0 to 100 against a configurable set of outreach quality rules and prints a report you can read, pipe as JSON, or gate CI on.

## Problem and result
Cold-outreach batches drift. The first drafts are hand-written. Later in the batch they share an opener skeleton, the closers repeat, a merge placeholder slips through, and every follow-up re-asks the first touch's question with the nouns swapped. Reply rates fall and nobody can say why, because each draft looks fine on its own.

outreach-lint measures that drift. Nine rules read one draft at a time, four batch rules compare drafts against each other, and one rule checks that a follow-up advances the thread instead of repeating it.

The result is a score and a list of findings for every draft. On the committed example batch, six synthetic drafts written off one skeleton, the run reports a mean score of 35 and 35 findings. The clean example draft scores 100 with none. The suite has 108 tests and covers 97% of the code, against a 90% gate in CI. The whole tool runs without an API key, and the optional model check stays off unless you ask for it.

### How it works
A run loads the drafts, merges the config, runs every enabled rule and scores each draft.

```
draft files (.md .txt .json .jsonl) ──▶ loader ──▶ drafts
shipped defaults + optional user TOML ──▶ validated config
                                              │
drafts + config ──▶ 9 per-draft rules  ──┐
                ──▶ 4 batch rules      ──┼──▶ findings ──▶ score per draft ──▶ text or JSON report
                ──▶ 1 follow-up rule   ──┘       ▲                              and an exit code
                                   optional LLM voice check (--llm)
```

* **Rule registry.** Rules register themselves with a decorator (`@rule("spam_phrases", scope="draft")`), so the orchestrator, the config and the CLI never import a rule by name. Adding a rule is one function plus one config model.
* **Pure rules.** Every rule takes a draft, or the batch, plus the merged config and returns findings. No IO and no state. All IO lives in `loader.py`, `cli.py` and `llm.py`.
* **Pydantic models.** Drafts, findings, reports and the whole config tree are Pydantic v2 models with `extra="forbid"`, so a typo in a config key or a draft record fails at the boundary with an error message.
* **Scoring.** A draft starts at 100 and loses points per finding by severity (error 25, warning 10, info 3) or by the rule's own weight, and the score stops at 0. A batch-rule finding counts against the draft it attaches to.

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

## Decision log
**1. Pure rules behind a registry.**
Chosen: each rule is one function that takes a draft, or the whole batch, and returns findings. A decorator registers it, and the orchestrator, the config tree and the CLI never import a rule by name. IO stays in three modules.
Known limits: a new rule needs a config model as well as a function. Batch rules say nothing useful about templating unless the run holds at least two drafts.

**2. Readability is computed in the repo.**
Chosen: Flesch reading ease and the Flesch-Kincaid grade are implemented in `textutil.py` with a vowel-group syllable heuristic.
Rejected: pulling in a readability dependency. The module notes that a stable result matters more for a linter than dictionary-perfect syllable counts.
Known limits: the syllable count is approximate for loanwords.

**3. Follow-ups are checked for negative signals only, and only as a warning.**
Chosen: `followup_advances` flags a follow-up that re-pitches, escalates assumptions beyond the first touch, or re-asks the first touch's question in other words. It stays a warning and never an error.
Rejected: judging whether a follow-up is a genuine bump. The module notes that no static check can make that call reliably.
Known limits: the re-asked question check needs the first touch in the same run, matched by `sequence_id`, and skips silently when it is missing.

**4. Strict config and strict input.**
Chosen: the shipped `default_config.toml` is the canonical ruleset. A user TOML is deep-merged over it and the result is validated, so an unknown key, bad TOML or an invalid regex stops the run with exit code 2 instead of being ignored. The loader does the same for drafts: an unknown front-matter key, an unterminated block or malformed JSON names the file and line.
Known limits: tables merge, but a list in your file replaces the shipped list, so extending a lexicon means restating the items you want to keep.

**5. The score stops at 0.**
Chosen: every finding deducts a weight from 100, and the result is clamped at 0. Findings from batch rules count against the draft they attach to.
Known limits: once a draft reaches 0 the score no longer separates a bad draft from a worse one. In the example batch tpl-a1 has 7 findings and tpl-a2 has 9, and both score 0.

**6. The model check is opt-in.**
Chosen: `--llm` adds one model call per draft and needs `ANTHROPIC_API_KEY` in the environment. Without a key it prints a notice and skips. If a call fails, that draft is reported and the run goes on. The key is read when the call is made and never logged, and model output is parsed defensively, so malformed output becomes one info finding.
Known limits: the test suite fakes the API boundary, so the keyed path is not exercised by the tests.

**7. The examples are test fixtures.**
Chosen: the tests assert that the clean example scores 100 and that the templated batch keeps tripping the templating rules, so the behavior the examples show cannot change silently. An autouse test fixture strips the CI environment markers and sets `NO_COLOR`, because Rich forces color when it sees `GITHUB_ACTIONS` and that broke output assertions in CI.
Known limits: the tests pin which rules fire and the clean score, not the finding counts. The numbers in this README come from a run, and changing a rule's threshold can change them.

## How AI was used
_Placeholder. The repository author writes this section._

## Run it locally
You need [git](https://git-scm.com/) and Python 3.11 or newer (CI runs 3.11, 3.12 and 3.13). Install into a virtual environment so the `outreach-lint` command lands on your path. It needs no key and no account.

```bash
git clone https://github.com/vybetechlabs-blip/outreach-lint.git
cd outreach-lint
pip install -e .
outreach-lint --help
```

Then lint the committed examples. The comment on each line is the exit code:

```bash
outreach-lint examples/good_t1.md                    # lint one draft: exit 0
outreach-lint examples/templated_batch.jsonl         # lint a batch, which enables the batch rules: exit 0
outreach-lint examples/templated_batch.jsonl --json  # machine-readable output: exit 0
outreach-lint examples/ --fail-under 70              # gate CI on a folder: exit 1, because the templated batch scores below 70
outreach-lint examples/good_t1.md --fail-under 70    # exit 0, the clean draft scores 100
```

Exit codes: `0` for a finished run, including one with findings when `--fail-under` is not set; `1` when a draft scores below `--fail-under`; `2` for input or config that cannot be read, such as a missing path, an unknown key or invalid TOML.

### Input formats
Drafts are plain text plus optional metadata: `touch` (`T1` to `T4`), `sequence_id` (groups one prospect's touches), and `hook` (the specific personalization anchor the draft is built on).

**Markdown or plain text** with optional YAML front-matter:
```markdown
---
touch: T1
sequence_id: seq-harborpine
hook: their June post about doubling the shop floor
---
Hi Mara,

Saw your June post about doubling the shop floor...
```

**JSON or JSONL**, with one object per draft carrying the body and the same metadata:
```json
{"id": "tpl-a1", "touch": "T1", "sequence_id": "seq-alpha", "body": "..."}
```

### Worked example
`examples/templated_batch.jsonl` is a deliberately bad batch: six synthetic drafts written off one skeleton, with a leftover merge token, a pitchy first touch, and a T2 that re-asks T1's question. This is the real output for two of the six drafts and the closing line. The tool prints an em dash between the draft id and the score, and prints backslashes in the path on Windows. Both are shown here as a hyphen and a slash.

```text
$ outreach-lint examples/templated_batch.jsonl
...
tpl-a2 - 0/100  examples/templated_batch.jsonl
  error   sequence_no_reuse: opener reused within sequence 'seq-alpha' (first 
used in 'tpl-a1')
  error   sequence_no_reuse: closer reused within sequence 'seq-alpha' (first 
used in 'tpl-a1')
  warning opener_variety: opener nearly identical to draft 'tpl-a1' (similarity
1.00)
  warning closer_round_robin: closer reused from draft 'tpl-a1' before 2 other 
closers ran
  warning followup_advances: follow-up re-pitches instead of advancing: "book a
call" (line 1)
  warning followup_advances: follow-up re-pitches instead of advancing: 
"pricing" (line 1)
  warning followup_advances: follow-up escalates assumptions beyond T1: 
"clearly you" (line 1)
  warning followup_advances: re-asks T1's question in reworded form (similarity
1.00): 'Open to comparing notes this week?'
  warning personalization_present: no personalization anchor: hook field empty 
and no specific reference found

tpl-b1 - 50/100  examples/templated_batch.jsonl
  warning opener_variety: opener nearly identical to draft 'tpl-a1' (similarity
0.79)
  warning opener_variety: opener nearly identical to draft 'tpl-a2' (similarity
0.79)
  warning closer_round_robin: closer reused from draft 'tpl-a1' before 2 other 
closers ran
  warning anti_formula: shares a structural formula with 3 other draft(s): 
'tpl-a1', 'tpl-b1', 'tpl-b2', 'tpl-c1'
  warning personalization_present: no personalization anchor: hook field empty 
and no specific reference found
...
batch: 6 drafts | mean score 35 | 35 findings
```

The six drafts score 0, 0, 50, 70, 60 and 30, which gives the mean of 35. The clean example passes untouched:
```text
$ outreach-lint examples/good_t1.md
good-t1 - 100/100  examples/good_t1.md
  no findings
```

### Rules
Severity weights are configurable: an error deducts 25 points, a warning 10 and an info 3. Every rule can be disabled (`enabled = false`) or re-weighted (`weight = N`, which overrides the severity weight) under its `rules.<id>` table.

**Per-draft rules.** Nine rules run once for each draft. Each one reads only that draft and the merged config.

| Rule id | Checks | Default severity | Key config |
| --- | --- | --- | --- |
| `spam_phrases` | Spam-trigger phrases ("free", "act now", "risk-free" and others) and excessive `!` | warning | `phrases`, `max_exclamations` |
| `unfilled_tokens` | Leftover merge placeholders in double-curly, single-curly, double-square, percent-wrapped and double-angle styles | **error** | `patterns` (regexes) |
| `personalization_present` | A populated `hook` field, or a detectable specific reference in the body (quoted phrase, number, URL, mid-sentence proper noun) | warning | none |
| `length_band` | Word count inside a target band; cold first-touches run short | warning | `min_words` (40), `max_words` (120) |
| `reading_level` | Flesch-Kincaid grade above a ceiling, or Flesch reading ease below a floor (over-polish reads machine-generated) | warning | `max_grade` (9.0), `min_reading_ease` (50.0) |
| `hedge_count` | More than one hedge ("maybe", "perhaps", "my guess" and others) | warning | `lexicon`, `max_hedges` (1) |
| `banned_constructions` | Configurable regexes for phrasings you know you template (seed: "before X becomes the constraint") | warning | `patterns` (regexes) |
| `t1_no_pitch` | On `touch = T1`: pitch, CTA and pricing phrases, and any automate, automating or automation | **error** | `pitch_phrases` |
| `banned_in_opener_closer` | The words automate, automating and automation in the first or last sentence, with the position named | warning | none |

**Batch rules.** Four rules compare drafts against each other, so they need at least 2 drafts in one run to say anything.

| Rule id | Checks | Default severity | Key config |
| --- | --- | --- | --- |
| `opener_variety` | Near-identical opener constructions across drafts (n-gram overlap on the normalized first sentence); reports the colliding pair | warning | `ngram_size` (3), `similarity_threshold` (0.6) |
| `closer_round_robin` | A closer reused before `window - 1` other closers have run (rolling window over batch order) | warning | `window` (3) |
| `sequence_no_reuse` | Within one `sequence_id`, an opener or closer reused across touches | **error** | none |
| `anti_formula` | Clusters of drafts sharing a structural formula in the opening move (bigram overlap over the first `prefix_words` words); reports the whole cluster | warning | `prefix_words` (30), `ngram_size` (2), `similarity_threshold` (0.4), `min_cluster_size` (3) |

**Follow-up rule.** One rule checks follow-up touches. It is registered as a batch rule so that it can see the first touch of the same sequence.

| Rule id | Checks | Default severity | Key config |
| --- | --- | --- | --- |
| `followup_advances` | T2 to T4 drafts that re-pitch, escalate assumptions beyond T1, or re-ask T1's question in reworded form (needs T1 in the same run, matched by `sequence_id`) | warning, never an error, because it is heuristic | `pitch_phrases`, `escalation_cues`, `question_similarity_threshold` (0.6) |

The heuristics behind `followup_advances` are documented in the module docstring of [`outreach_lint/rules/followup.py`](outreach_lint/rules/followup.py). It flags negative signals it can detect with reasonable precision and makes no claim to judge what a genuine insight is.

### Configuration
The shipped defaults live in [`outreach_lint/default_config.toml`](outreach_lint/default_config.toml), the canonical reference for every knob. Point `--config` at your own TOML to override any subset. Your file is deep-merged over the defaults and the result is validated, so unknown keys and invalid regexes fail loudly instead of doing nothing. `examples/user_config.example.toml` is a fuller version of this one:

```toml
# mine.toml
scoring.warning = 15.0                  # make warnings sting more
rules.length_band.max_words = 140
rules.reading_level.enabled = false     # turn a rule off
rules.unfilled_tokens.weight = 40.0     # re-weight one rule's findings
```

Save that as `mine.toml` and run it:
```bash
outreach-lint examples/ --config mine.toml                              # exit 0
outreach-lint examples/ --config examples/user_config.example.toml      # exit 0
```

List values replace the shipped list, because TOML has no append. Include the defaults you want to keep when you extend a lexicon.

### Optional model check
`--llm` adds one model call per draft that rates four voice dimensions: peer-to-peer against vendor-to-prospect, curiosity against diagnosis, over-polish, and grounding integrity (specific claims must be category patterns, never invented facts about this recipient's internals). Low scores and ungrounded claims become ordinary findings that deduct from the score.

The tool is fully functional without it, and all 14 rules are plain Python and deterministic. The check needs `ANTHROPIC_API_KEY` in the environment (`.env.example` names it) and the Anthropic package. Without a key, `--llm` prints a notice and skips.

```bash
pip install anthropic
outreach-lint examples/good_t1.md --llm   # exit 0; with no key set it prints the notice and skips
```

The model is configurable through `rules.voice_check.model`. The key is read from the environment when the call is made and is never logged. The tests never make network calls.

### Development
```bash
pip install pytest pytest-cov ruff mypy   # the dev tools named in pyproject.toml
pytest                                     # 108 tests, with a coverage report
ruff check .
ruff format --check .
mypy outreach_lint
```

`make check` runs the same four checks where `make` is installed, and `make fmt` formats the code. CI runs them on Python 3.11, 3.12 and 3.13 with a 90% coverage gate, then lints the example batch as a smoke test.

License: MIT, see [LICENSE](LICENSE). All example and fixture data is synthetic: invented names, invented companies. No real prospect data, no PII, and no secrets live anywhere in this repository or its history.

## Status
**Status: Complete.** The 108 tests pass at 97% coverage, and CI runs ruff, mypy and pytest on Python 3.11, 3.12 and 3.13. Known limits are listed in the decision log.
