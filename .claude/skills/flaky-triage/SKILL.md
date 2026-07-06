---
name: flaky-triage
description: When a test goes red then green with no intervening code change, confirm it's flaky, record it in the registry, and optionally quarantine it so it stops blocking PRs but stays visible — instead of silently blocking the queue or being silently ignored
cost: cheap
protects: "A test that turns red then green gets confirmed as flaky, logged, and optionally quarantined instead of silently blocking or being ignored."
requires: nothing
gate_key: flaky_triage
ci_job: none
---

# Flaky Test Triage

**Profile-driven.** This skill reads `flaky.*` keys from `.claude/kit.yaml` (listed in [Profile keys](#profile-keys) below) and `toolchain.test` for the base runner command.

> **Mode.** This gate runs per `gates.modes.flaky_triage` in `.claude/kit.yaml`:
> `enforce` — run, block on failure; `suggest` — surface it at the natural
> moment with the `protects:` sentence and cost class above, run only on
> acceptance, and record accept/decline in the gate ledger
> (`.claude/scratch/gate-ledger.md`, SPEC.md §8.2) — never skip silently;
> `off` — not offered. Key absent → derive from `gates.strictness` per the
> table in `docs/PROFILE.md`. (SPEC.md §4.1, §4.4)

A test that passes on re-run with no code change is not noise — it is a latent reliability bug. This skill confirms the flakiness with a systematic re-run, files a durable follow-up so the finding is not lost, and optionally quarantines the test so it stops burning CI time while remaining visible to `nightly-audit`. Triggered by `ci-watch` (red→green, no change) or by a human who notices the same pattern.

## Profile keys

| Key | Default | Meaning |
|---|---|---|
| `flaky.rerun_count` | `5` | Number of times to re-run the suspect test node |
| `flaky.flaky_threshold` | `0.8` | Pass-rate ceiling for a flaky verdict (exclusive); range 0.0–1.0 |
| `flaky.marker` | `"flaky"` | Pytest marker name applied when quarantining |
| `flaky.quarantine_allowed` | `false` | When false, skip quarantine and only record |
| `flaky.registry` | `"docs/flaky-tests.md"` | Registry file path relative to the repo root |
| `toolchain.test` | `"uv run pytest tests/unit/ …"` | Base runner; substitute `<nodeid>` for the path glob when re-running |

## Workflow

### 1. Identify the suspect node

The caller (ci-watch or a human) provides the test node ID — a string like
`tests/unit/test_scheduler.py::TestRetry::test_timeout`. If it is not known, grep
the CI failure log for the `FAILED` line:

```bash
# From `gh run view <run_id> --log-failed` output:
grep -E "^FAILED " ci-failed.log
```

### 2. Re-run and record the pass rate

Run the suspect node `flaky.rerun_count` times (default 5). Substitute the node ID
into the runner from the profile:

```bash
# kit.yaml → toolchain.test  (replace the path glob with <nodeid>)
PASSES=0
RUNS=5  # flaky.rerun_count
for i in $(seq 1 $RUNS); do
  uv run pytest <nodeid> -q --no-header 2>/dev/null && PASSES=$((PASSES + 1))
done
echo "Pass rate: $PASSES / $RUNS"
```

Compute pass rate = passes ÷ runs.

### 3. Render a verdict

| Pass rate | Verdict | Next step |
|---|---|---|
| `0` (never passes) | **Real failure** — not flaky | Stop. Report to the caller as a real failure; do not file a flaky entry. |
| `> 0` and `< flaky_threshold` | **Flaky** | Proceed to step 4. |
| `≥ flaky_threshold` | **Mostly-passes** — borderline | Proceed to step 4 with a borderline note; record but do not quarantine. |

`flaky_threshold` defaults to `0.8`. A test that passes 4 of 5 runs (0.8) is
borderline — record it and watch it; do not quarantine yet. A test that passes 2 of
5 runs (0.4) is clearly intermittent.

### 4. File a follow-up

Use the **followup-tracking** skill to append an entry to `docs/followups.md`
(resolved from `capabilities.docs.dir` in `kit.yaml`, default: `docs`). Assign a
stable ID with the prefix `FLAKY-` and a short slug derived from the node id
(e.g. `FLAKY-scheduler-timeout`):

```markdown
### FLAKY-<slug> — <test short name> is intermittent

- **Spec:** `flaky.registry` registry entry; owner: <assignee or unassigned>
- **Status:** open
- **Gap:** `<nodeid>` passed <N>/<M> re-runs (pass rate <P%>). No code change
  between the red and green runs. Needs root-cause investigation and a fix or
  explicit deletion. Quarantine status: <quarantined | not quarantined>.
```

Note the follow-up ID — you will write it into the registry in step 6.

### 5. Quarantine (optional)

Skip this step entirely if `flaky.quarantine_allowed` is `false` (default), or if
the verdict from step 3 is **Mostly-passes** (borderline).

If quarantine is allowed and the verdict is **Flaky**:

**a. Add the marker to the test source.**

Open the test file and add `@pytest.mark.<marker>` (default: `@pytest.mark.flaky`)
directly above the test function or class. If the marker is not registered in
`conftest.py` or `pyproject.toml`, add the registration now.

**b. Verify the marker is excluded from the gating run.**

Check that `toolchain.test` in `kit.yaml` includes `-m 'not <marker>'`. If it does
not, add the exclusion now and note the change in your output.

**c. Confirm the test still runs somewhere.**

The marker must be included in at least one non-gating run — for example, a nightly
suite or a manual `pytest -m <marker>` invocation. If no such run exists, add a
follow-up item noting this gap: a quarantined test that never runs is a deleted test
with extra steps.

### 6. Update the registry

Append a row to the registry file (`flaky.registry`, default `docs/flaky-tests.md`).
If the file does not exist yet, create it from `docs/flaky-tests.template.md`.

| Test node id | Pass rate | First seen | Quarantined? | Follow-up ID | Owner |
|---|---|---|---|---|---|
| `<nodeid>` | `<N>/<M> (<P%>)` | `<YYYY-MM-DD>` | Yes / No | `FLAKY-<slug>` | <assignee or —> |

## Guardrails

- **Quarantine is a loan, not forgiveness.** Every quarantined test must have an
  owning follow-up ID in the registry. `nightly-audit` surfaces the total
  quarantined count and the age of each entry so the list cannot grow unnoticed.
  A quarantined test that still has an open follow-up after 30 days should be
  escalated by `nightly-audit`, not quietly carried forever.
- **Never quarantine without recording.** If `quarantine_allowed` is true but the
  registry update fails for any reason, revert the marker change. An unrecorded
  quarantine is worse than no quarantine — it is a silently deleted test.
- **Do not quarantine a real failure.** A test that never passes (pass rate = 0) is
  broken, not flaky. Fix it or delete it; do not quarantine it.
- **Borderline tests are recorded, not quarantined.** If a borderline test (pass
  rate ≥ `flaky_threshold`) surfaces again on a subsequent run, the accumulated
  evidence justifies reopening triage and potentially quarantining then.
- **Never widen `flaky_threshold` retroactively** to reclassify a failing test as
  flaky. The threshold is a project-wide policy in `kit.yaml`, not a per-test
  escape hatch.

## Output

```
## Flaky Triage

- Test node:      <nodeid>
- Reruns:         <N> (flaky.rerun_count)
- Pass rate:      <passes>/<N> (<P%>)
- Verdict:        Flaky | Mostly-passes (borderline) | Real failure (not flaky)
- Follow-up filed: <FLAKY-slug> | none (real failure)
- Quarantine:     applied (<marker> marker added) | skipped (quarantine_allowed=false) | skipped (borderline) | n/a (real failure)
- Registry updated: yes (<flaky.registry>) | no
```
