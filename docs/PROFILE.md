# The Project Profile (`.claude/kit.yaml`)

The profile is what makes the kit portable across languages and project types.
Instead of every skill hardcoding `uv run pytest`, skills read commands and
capability toggles from one file — `.claude/kit.yaml` — so adapting the kit to a
Node, Go, or Rust project (or a library vs. a deployed service) is a matter of
editing that one file, not a dozen skill bodies.

## How skills consume the profile

Skills are instructions to an agent, not compiled code, so consumption is by
convention, not a templating engine:

1. **Toolchain commands.** A step is tagged with the profile key it resolves to:

   ````
   ### 3. Tests
   ```bash
   # kit.yaml → toolchain.test
   uv run pytest tests/unit/ -m "not slow and not llm" --tb=short -q
   ```
   ````

   The executing agent runs the command from `kit.yaml` if the key is set; the
   literal shown is the **default** (a Python/uv project). An empty string in the
   profile means **skip this step** and mark it N/A.

2. **Capability gates.** A capability-specific skill checks its toggle first:

   > **Applies when** `capabilities.migrations.enabled` is true. If false, skip
   > and report N/A.

   This is how `pre-pr` runs the right subset: an LLM service runs eval /
   prompt-regression / cost gates; a Go CLI runs none of them, with no edits.

3. **Named values.** `trunk_branch`, `worktree_dir`, `alerts.channel`, and
   `capabilities.spec.file` are read wherever a skill or hook needs them.
   The `logging.*` block records what the `logging-init` skill probed, asked,
   and wired (library, destination, dev rendering) — `initialized: false` is a
   standing kit-doctor warning to run it.

## Gate modes — enforce, suggest, off

Every gate runs in one of three **modes** (SPEC.md §4.1), and the mode — not the
gate's identity — decides whether it blocks, asks, or stays silent:

| Mode | Behavior |
|---|---|
| `enforce` | Run; **block** on failure, without asking. Reserved for gates that are cheap, deterministic (same diff → same verdict), and protect against a failure that is expensive to reverse or corrupts shared state (SPEC.md §2.2). |
| `suggest` | Surface the gate at its natural moment with its `protects:` sentence and cost class, run it **on acceptance**, and record every decline. A suggest gate is **never silently skipped** — surfacing it is mandatory (SPEC.md §2.6); only a human may decline, and the decline is logged to the gate ledger (§ below). |
| `off` | Not offered at all. `kit-doctor` lists every off-gate in a one-line footer so the choice stays visible rather than forgotten. |

Skills read the mode once at the start of a run. A skill that changes behavior
by mode says so in its body; a skill with no mode-specific behavior treats
`enforce`/`suggest` as run-and-block vs. run-on-acceptance and `off` as N/A.

## Resolution is materialized, not computed

`gates.strictness` does **not** get evaluated at runtime. It selects which
**fully-populated** `modes:` block bootstrap (or `/kit-menu`) writes into
`kit.yaml` — strictness only picks the defaults; the written map is the source
of truth (SPEC.md §4.4). Every gate skill reads **exactly one key**,
`gates.modes.<its gate_key>`, with a single fallback sentence:

> Key absent → derive from `gates.strictness` per the table below.

A partial, hand-edited map is therefore legal — edit any one line to override
that gate — but the tooling never produces one: init always writes every key
from SPEC.md §4.2, one per line, two-space indent, no flow style.

```yaml
gates:
  strictness: "standard"
  modes:                    # fully written by init; edit any line to override
    secrets_scan: enforce
    security_review: suggest
    # … every key, one per line
```

## The strictness invariants

The default map each strictness level selects is not free-form; it must satisfy
these invariants (SPEC.md §4.3), which is what preserves "no behavior change
until a `modes:` block is written":

- **Deterministic-protective gates** — `secrets_scan`, `credential_files`, and
  `migration_check` — are `enforce` at **every** level. These are the
  hard-safety gates that blocked at every level under v1, and they still do.
- **CI-backed gates** — any gate whose `ci_job` is not `none` (lint/types/tests
  today; the coverage/perf ratchets once they move authoritatively into CI) —
  are pinned `enforce` at every level. A mode map may not demote them, or
  "green locally = green PR" inverts into "optional locally, red in CI"
  (SPEC.md §2.3).
- `prototype` demotes **only** the trend and subagent gates (coverage / perf /
  eval, security review, doc/observability reviewers) to `suggest`.
- `production` sets **everything installed** to `enforce`.
- **Preset overlays.** A preset may override its archetype's defaults: `llm-app`
  pins `prompt_regression` (and the eval pass-gate) to `enforce` so the target
  persona's core protection is never advisory; team-shaped presets default
  `worktree_isolation: enforce` while `library`/solo contexts default it to
  `suggest`.

Security review is therefore **suggest-class** (its cost is a subagent dispatch)
at every level **except** `production` strictness, where everything installed —
security review included — is `enforce`. There is no level at which security
review "always blocks" independent of the mode map.

### Strictness default maps (generated)

The three-column table below (gate × prototype/standard/production) is generated
from skill frontmatter by `scripts/gen-catalog.sh` and written between the
markers; `kit-ci` fails if regeneration produces a diff, so the documented
defaults can never drift from what init actually writes.

<!-- modes:begin -->
| Gate key | prototype | standard | production |
|---|---|---|---|
| branch_conflict | enforce | enforce | enforce |
| build_artifact | enforce | enforce | enforce |
| capture | enforce | enforce | enforce |
| coverage_ratchet | suggest | enforce | enforce |
| credential_files | enforce | enforce | enforce |
| docs_sync | suggest | suggest | enforce |
| flaky_triage | enforce | enforce | enforce |
| integration_tests | enforce | enforce | enforce |
| lint_types_tests | enforce | enforce | enforce |
| migration_check | enforce | enforce | enforce |
| observability_check | suggest | suggest | enforce |
| perf_budget | suggest | enforce | enforce |
| prompt_regression | suggest | suggest | enforce |
| secrets_scan | enforce | enforce | enforce |
| security_review | suggest | suggest | enforce |
| spec_drift | suggest | suggest | enforce |
| sync_health | enforce | enforce | enforce |
| test_gap | suggest | suggest | enforce |
| ui_build | enforce | enforce | enforce |
| worktree_isolation | enforce | enforce | enforce |

_Preset overlays (SPEC.md §4.3): `llm-app` pins `prompt_regression` to enforce; `library`/solo presets default `worktree_isolation` to suggest._
_generated by scripts/gen-catalog.sh --modes — the normative copy lives in docs/PROFILE.md once §4 ships_
<!-- modes:end -->

## Cost classes

Menus and gate offers price work by **class**, not dollars — an order of
magnitude, not a measured figure (SPEC.md §5; measured per-run pricing is
deferred, SPEC.md §13):

| Class | What it spends |
|---|---|
| `free` | File edits only — reads and writes, no model usage beyond the invoking turn. |
| `cheap` | Bounded project commands (lint, types, tests) — seconds to minutes of local CPU, no extra model spend. |
| `subagents` | Agent dispatches and/or live model calls (an eval run counts even with zero dispatches). The only class that spends real money at run time. |

A skill's `cost:` field is worst-case-when-accepted; a two-phase skill prices
its expensive phase and the report says which phase actually ran.

## The kit.yaml parse contract

Every key the bash layer reads — hooks and `scripts/kit-config.sh` — obeys a
deliberately small YAML subset (SPEC.md §10.3): two-space indent, one
`key: value` per line, no flow style, no anchors, and single-line
double-quoted strings. `kit-ci` validates the shipped `kit.yaml` and every
preset against this contract. It is what makes `gates.modes.<key>` reliably
grep-able from a hook or from `scripts/kit-config.sh get <dotted.key>` without a
YAML parser.

## Unattended sessions

Non-interactive runs (cron, `nightly-audit`, `pr-babysitter`, headless CI
sessions) cannot consent live, so they get a fixed rule (SPEC.md §6.4): the
`enforce` set runs as always; every `suggest` gate is **skipped and logged** —
the run report lists it as "not offered — unattended" — and nothing is
auto-accepted. A per-gate `gates.unattended.<gate_key>: run|skip` override in
`kit.yaml` is where the human who scheduled the automation pre-consents specific
suggest gates at configuration time; absent that, unattended never turns a
suggestion into an action.

## The gate ledger

Suggest-mode accept/decline events append to a **git-ignored, per-clone** ledger
at `.claude/scratch/gate-ledger.md` (SPEC.md §8.2) — append-only machine lines
of the form `YYYY-MM-DD PR#<n> <gate_key> accepted|declined`. Fatigue is
personal, so the counters are per-clone and never committed; the committed mode
map is team policy and changes only by PR.

## Gate strictness for a run

Bootstrap starts brand-new repos at `prototype` strictness with a TODO to
graduate; presets default to `standard`. Move the level up deliberately — but
remember the level only chooses which default map init *wrote*; once written, the
`gates.modes:` block is authoritative and any single line can be overridden
without changing `strictness` at all.

## Where the profile comes from

- **New projects:** `new-project-bootstrap` detects the stack (probes for
  `pyproject.toml` / `package.json` / `go.mod` / `Cargo.toml`, reads existing CI
  or a Makefile for the real commands) and writes `kit.yaml`, picking a **preset**
  as the starting point.
- **Existing projects:** `adopt-existing-project` infers the profile from what's
  already there and merges rather than overwrites.
- **Presets** (`presets/*.yaml`) are archetype defaults — `library`, `service`,
  `llm-app`, `frontend`, `data-pipeline` — each enabling a curated capability set.

## Keeping it honest

`kit-doctor` runs 15 checks that verify the profile is wired correctly: every
non-empty toolchain command actually runs, capability toggles match what's
installed, hooks are executable and referenced in settings, `gh` is authed, and
the §3 additions — skill metadata completeness, each `ci_job` resolving to a
real CI job, the coverage baseline, and the file-hash manifest. Run it after any
profile edit. The bash layer reads keys through `scripts/kit-config.sh get
<dotted.key>` (a Tier-0 reader honoring the parse contract above), so a
malformed `kit.yaml` fails loudly rather than silently mis-parsing. `kit-update`
compares `kit_version` against the source kit so improvements to a skill
propagate instead of silently drifting.
