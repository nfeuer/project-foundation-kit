---
name: eval-harness
description: Set up and run tiered, version-controlled evaluation fixtures for non-deterministic behavior (LLM calls, classifiers, extractors) — score against pass-gates and catch regressions in CI
---

# Eval Harness

**Applies when** `capabilities.llm.enabled` is true (else skip, report N/A).

**Profile-driven.** The fixture root directory is `capabilities.llm.eval_dir` from `.claude/kit.yaml` (default: `fixtures`).

Unit tests check deterministic code. This skill covers the parts that don't have
one right answer — anything backed by a model, a classifier, or a fuzzy
extractor. The pattern: version-controlled fixtures, tiered by difficulty, scored
against a pass-gate, run offline with mocked tools, and gated in CI.

Use it when adding or changing any capability whose output is judged rather than
asserted.

## Structure

Fixtures live at `<eval_dir>/<task_type>/tier<N>_<name>.json`, one file per tier
(where `eval_dir` = `capabilities.llm.eval_dir` from `kit.yaml`, default: `fixtures`).
See `templates/eval_fixture.example.json` for the shape. Each file declares a
`pass_gate` (fraction of cases that must pass) and a list of `cases`, each with
an `input`, an `expected` output, and optional `tool_mocks` for offline runs.

### Tiers
- **Tier 1 — baseline.** Simple, unambiguous. `pass_gate: 0.90`. A regression
  here blocks the merge.
- **Tier 2 — nuance.** Domain-specific judgment calls.
- **Tier 3 — complexity.** Compound / multi-part inputs.
- **Tier 4 — adversarial.** Contradictions, buried tasks, edge cases.
  `pass_gate: null` — diagnostic only, tracked but not gated, so a hard-case
  failure doesn't block shipping while a baseline regression does.

## Workflow

### 1. Author fixtures before (or with) the capability
Write the expected outputs for the cases you care about. For anything that calls
a tool (calendar, email, search), add `tool_mocks` keyed by tool fingerprint so
the eval runs deterministically offline — no live API calls, no spend, no
flakiness.

### 2. Score with schema validation first, then correctness
Validate each output against its JSON schema (`schemas/<task_type>.json`) — a
malformed output is an automatic fail. Then compare against `expected`. For
fuzzy fields (free text), score with an LLM-judge rather than exact match: send
the prompt + output to a judge model and take its `quality_score` (0.0–1.0),
flagging anything below threshold.

### 3. Compute the tier result
```
passed / total >= pass_gate  →  tier PASS
```
Report per-tier and per-case so a regression points at the exact case.

### 4. Gate in CI
Run tiers 1–2 (the gated ones) in CI on the `not slow and not llm` marker set
using mocked tools, so the suite is fast and free. Run the full set (including
live-model tiers) on a schedule or a label, not on every push.

## When you change a prompt or model
Re-run the harness before and after. A prompt tweak that helps one tier can
regress another — the fixtures are how you find out before your users do. Record
notable score deltas in `docs/followups.md` if you accept a tradeoff.

## Output
```
## Eval Run — <task_type>
| Tier | Cases | Passed | Gate | Result |
|------|-------|--------|------|--------|
| 1 baseline | 20 | 19 | 0.90 | PASS |
| 2 nuance   | 15 | 11 | 0.80 | FAIL |
Failing cases: <ids + why>
Verdict: PASS / REGRESSION — <detail>
```
