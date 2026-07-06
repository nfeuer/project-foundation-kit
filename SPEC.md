# Kit v2 — Consent-First Design Spec

**Status:** reviewed draft (rev 2 — incorporates the adversarial design review
and the implementability review) · **Supersedes:** the implicit v1 design
(install everything, enforce by default) · **Evidence base:** the 2026-07-06
five-persona friction test (findings PT1–PT11 in `docs/followups.md`).

This is the kit's canonical spec. Skills, PRs, and ADRs cite sections as
`SPEC.md §N`.

---

## §1 Motivation

Five personas walked the v1 kit. The convergent findings:

1. **Unconsented cost.** Bootstrap installs all ~30 skills; `pre-pr` runs 17
   steps with ≥4 subagent dispatches on every PR regardless of diff size
   (estimated $600–2,400/month at 10 PRs/day); the 1% rule forbids the middle
   path, so overloaded users abandon the system wholesale rather than trim it.
2. **Unstated prerequisites.** The LLM-flagship skills assume substrate that
   doesn't ship (spend table, eval runner, alert transport, an always-on
   scheduler). Users discover this at first failure, not at install.
3. **One global posture.** Everything is either enforced or absent. There is
   no way to say "suggest the security review, enforce the secrets scan."
4. **Agnosticism inverted.** The stack-free *machinery* was Python-dependent,
   while the stack-deep *content* (templates, CI) pretended to be agnostic.
5. **Wrong-audience surfaces.** Every question, block message, and report
   assumes a mid-level engineer, even though Claude — not the human — is the
   real operator of most of them.

v2's thesis: **the kit's practices were right; its posture was wrong.** Keep
the practices. Change how they are offered, priced, and enforced.

## §2 Design principles

1. **Consent before cost.** Nothing that costs tokens, time, or workflow
   friction turns on without the user having seen what it does and what it
   costs — once, at init, in plain language. For unattended sessions, consent
   is given once, at configuration time, by the human who scheduled them (§6.4).
2. **Enforce only the deterministic and protective.** A gate may block without
   asking only if it is (a) cheap, (b) deterministic (same diff → same
   verdict), and (c) protecting against a failure that is expensive to reverse
   **or corrupts shared state**. Today that set is: secrets scan,
   credential-file guard, migration heads, and — where enabled — worktree
   isolation. Judgment-based or subagent-dispatching gates default to
   suggestion.
3. **CI is law; local is advice.** Any gate with an authoritative CI job is
   **pinned enforce locally at every strictness level** — a mode map may not
   demote it, or "green locally = green PR" inverts into "optional locally,
   red in CI." Ratchet- and baseline-shaped gates live authoritatively in CI
   (§8.3), where they are race-free and unskippable. Local runs make CI
   boring; they never substitute for it.
4. **Machinery agnostic, content tiered.** Everything needed to *operate* the
   kit (hooks, doctor, adopter, updater, init) runs on bash + git alone —
   bash helper scripts are permitted; Python is not (§10). Stack *content*
   (templates, CI jobs, language recipes) is explicitly tiered per §10.
5. **Claude is the operator; the human is the principal.** Machine-facing
   surfaces optimize for agent execution. Human-facing surfaces state
   outcomes and options in plain language, with jargon one level deeper.
   (This adapts *register*, not audience: a full non-engineer product is
   explicitly deferred — §13.)
6. **Suggestions must be surfaced; only humans may skip them.** The agent
   MUST present every triggered suggest-mode gate at its natural moment
   (§6.2) — the softening in v2 applies to the *decision*, never to the
   *surfacing*. An unsurfaced suggestion is a silent skip, which remains the
   kit's cardinal sin.

## §3 Skill metadata (the priced catalog)

Every SKILL.md frontmatter gains four required fields:

```yaml
---
name: prompt-regression
description: <unchanged — the trigger sentence>
cost: subagents      # free | cheap | subagents
protects: "Prompt or model changes ship with a before/after eval score instead of a vibe."
requires: "eval fixtures + a runner (SUBSTRATE.md §2); capabilities.llm.enabled"
gate_key: prompt_regression    # key in gates.modes (§4), or "none" for non-gates
ci_job: none         # name of the authoritative CI job, or "none" (§2.3, §8.3)
---
```

- `cost:` is **worst-case when accepted**. `free` — reads/writes files, no
  model usage beyond the invoking turn. `cheap` — runs bounded project
  commands (lint, tests). `subagents` — dispatches subagents **and/or makes
  live model calls** (eval runs count even with zero dispatches). A skill
  that MAY dispatch is `subagents`. For two-phase skills (pre-pr, §6), the
  field prices the expensive phase; the report says which phase ran.
- `protects:` — one sentence, outcome language, readable by a non-engineer.
  This is the sentence the init menu shows.
- `requires:` — substrate or capability preconditions (§9), or `nothing`.
- `gate_key:` — binds the skill to its mode-map entry. Skills with
  `gate_key: none` (session-handoff, writing-kit-skills, using-the-kit, adr…)
  are workflow/meta skills: never mode-gated, offered in the init menu's
  Guide group as conventions.
- `ci_job:` — names the CI job that is authoritative for this gate, if any.
  kit-doctor cross-checks: every `ci_job` value exists in the installed CI
  workflow, and every CI-backed gate is `enforce` in the active mode map.

**Generation contract.** Fields consumed by tooling are single-line,
double-quoted scalars. A bash generator (`scripts/gen-catalog.sh`, Tier-0)
regenerates the README workflow catalog between `<!-- catalog:begin/end -->`
markers and prints the strictness default maps for PROFILE.md; **kit-ci fails
if regeneration produces a diff.** The init menu (§5), the mode-map defaults
(§4), the README catalog, and the `ci_job` consistency check are all derived
from this metadata — one source of truth, mechanically enforced.

## §4 The gate mode map

### §4.1 Modes

Every gate runs in one of three modes: **enforce** (run; block on failure),
**suggest** (surface at the natural moment with `protects:` + cost class;
run on acceptance; record declines — never silently skip, §2.6), **off**
(not offered; kit-doctor lists off-gates in a one-line footer so they stay
visible).

### §4.2 The full key set

`secrets_scan`, `credential_files`, `worktree_isolation`, `lint_types_tests`,
`integration_tests`, `migration_check`, `coverage_ratchet`, `perf_budget`,
`security_review`, `test_gap`, `docs_sync`, `spec_drift`, `prompt_regression`,
`branch_conflict`, `observability_check`, `flaky_triage`, `sync_health`,
`ui_build`, `build_artifact`, `capture` (followups + learnings, §6.3).
Gates with no key do not exist: every gate-like behavior in the kit maps to
exactly one key (kit-doctor checks the `gate_key` fields cover this list).

### §4.3 Strictness → default maps

`gates.strictness` selects a **default map**; the normative three-column
table (gate × prototype/standard/production) lives in `docs/PROFILE.md` and
is generated from metadata (§3). The invariants the table must satisfy:

- **Deterministic-protective gates** (`secrets_scan`, `credential_files`,
  `migration_check`) are `enforce` at **every** level. (This preserves v1's
  actual prototype semantics — trend gates advisory, hard-safety gates
  blocking — so the migration claim in §12.1 is true.)
- **CI-backed gates** (`ci_job != none`: lint/types/tests, ratchets once
  §8.3 ships) are `enforce` at every level, per §2.3.
- `prototype` demotes only trend + subagent gates to suggest; `standard` is
  the shipped middle; `production` sets everything installed to enforce.
- **Preset overlays:** a preset may override defaults for its archetype —
  `llm-app` sets `prompt_regression` and the eval pass-gate to **enforce**
  (the target persona's core protection is not demoted to advisory), and
  team-shaped presets (`service`, `llm-app`, `data-pipeline`) default
  `worktree_isolation: enforce` while `library`/solo contexts default it
  to `suggest`.

### §4.4 Resolution is materialized, not computed

Skills do **not** re-implement precedence. Bootstrap / `/kit-menu` always
write a **fully-populated** `modes:` block into `kit.yaml` (strictness only
selects which defaults get written). Every gate skill reads exactly one key —
`gates.modes.<its gate_key>` — with one fallback sentence: "key absent →
derive from `gates.strictness` per the table in docs/PROFILE.md." A partial
hand-edited map is therefore legal but the tooling never produces one:

```yaml
gates:
  strictness: "standard"
  modes:                    # fully written by init; edit any line to override
    secrets_scan: enforce
    security_review: suggest
    # … every key from §4.2, one per line, two-space indent, no flow style
```

### §4.5 Hooks under the mode map

Three enforce-class gates are bash hooks. The parse contract (§10.3) applies:
hooks read `gates.modes.<key>` via the documented one-line grep/sed pattern.
Semantics: `enforce` = current blocking behavior; `suggest` = allow + stderr
warning (for `worktree_isolation` only — the two credential-shaped hooks are
never below enforce); `off` = the hook is **not installed**, and kit-doctor's
unreferenced-hook check whitelists hooks that are `off` in the mode map.

All five `presets/*.yaml` gain the commented `modes:` scaffolding.

## §5 The init interview (bootstrap v2)

Three acts; Acts 1–2 are read-only. `new-project-bootstrap` grafts Acts 1–2
between its detect and write steps; Act 3 replaces the `cp -r` install.

**Act 1 — Learn.** The existing detection/audit machinery runs. Output: an
evidence table.

**Act 2 — Explain.** The menu is rendered by the bootstrapping agent from
skill metadata: read the frontmatter of every `.claude/skills/*/SKILL.md`
(the §3 generation contract makes this a mechanical extraction), cross-join
with Act-1 evidence, group as **Protect** (recommend-enforce), **Guide**
(suggest + `gate_key: none` conventions), **Build-first** (`requires:` unmet
— shown with the prerequisite and its SUBSTRATE.md section; never installed
as a dud). Costs are shown as **classes only** (free/cheap/subagents), with
the order-of-magnitude class table maintained in `docs/PROFILE.md` — no
per-run dollar figures (measured pricing is deferred, §13).

> ● **Migration safety** — you have alembic migrations. Blocks a destructive
> migration before it hits your database. Cost: cheap. Recommended: enforce.
>
> ○ **Security review** — you make outbound HTTP calls. A reviewer agent
> audits auth/input-handling changes. Cost: subagents. Recommended: suggest.
>
> ✗ **Prompt regression** — requires eval fixtures (SUBSTRATE.md §2).
> Available later via `/kit-menu`.

At most three questions beyond menu choices. Register adapts to Act-1
evidence (solo repo, no CI ⇒ plainer language), per §2.5's cap.

**Act 3 — Choose & record.** Only chosen skills are copied (install-time
pruning). `kit.yaml` gets the fully-populated `modes:` block (§4.4), the
`triggers:` map (§6.1), and the declined list:

```yaml
declined:                  # keys share the gate_key namespace; skill name for non-gates
  prompt_regression: "no fixtures yet — revisit when LLM behavior matters"
  worktree_isolation: "solo repo, single session"
```

**Normative consumers of `declined:`** — (1) `using-the-kit`: suppress
trigger-index suggestions for declined keys; (2) `kit-update`: files whose
gate_key/skill name is declined are reported in a one-line DECLINED footer,
never offered as NEW; (3) `/kit-menu` (a new v2.0 skill that re-renders Act 2
against current evidence): shows them as "○ previously declined: <reason>".
Init-time declines do **not** seed §8's runtime counters — different consent
context.

**Pruning safety:** a skill invoked by name from another skill (pre-pr's
steps reference coverage-ratchet, migration-check, …) treats a missing skill
directory exactly as `mode: off` — collapsed to one summary line, never an
error. **Composition with adopt:** `adopt-existing-project` keeps its
four-phase temporal rollout; Act 3's menu output *is* the phased plan —
choices are recorded in `kit.yaml` immediately, installation still proceeds
phase-by-phase with per-phase approval.

## §6 Suggest-mode runtime

### §6.1 Triggers live in the profile

`kit.yaml` gains a `gates.triggers:` map — path globs per gate, written at
init from Act-1 evidence, matched against `git diff <trunk>...HEAD
--name-only`:

```yaml
gates:
  triggers:
    security_review: ["src/auth/**", "**/middleware/**", "**/*_client.py"]
    prompt_regression: ["prompts/**", "config/models*", "schemas/**"]
    docs_sync: ["src/**"]        # broad on purpose; agent judgment refines
```

Fallback where globs are absent: agent judgment per the trigger sentence in
the skill (documented as the fallback, not the mechanism).

### §6.2 Two-phase pre-pr

**Phase 1 (always):** the enforce-mode set — which by §4.3's invariants
always includes the deterministic-protective gates and every CI-backed gate.
**Phase 2:** compute the trigger set from the diff (§6.1) and present one
menu — the agent MUST present it (§2.6):

> Enforced gates passed (lint, types, tests, secrets).
> Recommended for this diff: **security-review** (touched `src/auth/`),
> **doc-sync** (changed public API). Also available: test-gap.
> Run all / pick / skip — skips are recorded.

A docs-only diff runs Phase 1 in three steps. The 17-step output block
survives with N/A rows collapsed to one summary line. Accept/decline events
are appended to the **local gate ledger** (§8.2).

### §6.3 Capture skills ride materiality triggers

Followups / compound-learnings / doc-sync suggestions fire on materiality
(diff touched docs; a debugging session exceeded the compound-learnings
threshold; spec-relevant behavior changed) — **not** on every unit of work.
They are one mode-map entry (`capture`) and ratchet down like any gate.

### §6.4 Unattended sessions

Non-interactive runs (cron, nightly-audit, pr-babysitter, headless CI
sessions) cannot consent live. Rule: run the enforce-mode set; **skip-and-log**
suggest-mode gates (the run report lists them as "not offered — unattended");
never auto-accept a suggestion or a ratchet proposal. A per-gate
`unattended: run|skip` override in `kit.yaml` lets the scheduling human
pre-consent specific gates at configuration time — that is where §2.1's
consent happens for automation.

## §7 Chaining replaces the 1% rule

1. **Canonical chain table** lives in `using-the-kit` (loaded every session):
   pre-pr → ci-watch → (merge) → capture; doc-sync → followup-tracking;
   incident-capture → adr; flaky-triage → followup-tracking. Per-skill
   `Next:` lines in every Output block cite that table and are written
   declined-aware ("Next: ci-watch (if installed)"). The
   config-consistency-checker agent verifies every `Next:` target exists or
   is declined.
2. **The trigger index stays**, contract per §2.6: when a trigger matches a
   suggest-mode gate, the agent MUST surface it; enforce-mode gates run
   without asking; declined keys are suppressed. The red-flags table is
   retained for enforce-mode gates only.

## §8 Earned enforcement & the CI backstop

### §8.1 Ratchet-up (propose enforce)

Based on **CI-side and accepted-run findings** — a gate that produced 2
blocking-grade findings within the window (last 10 runs recorded in the
ledger OR 30 days, whichever is smaller) triggers the proposal. CI findings
count even when the local gate was declined, so avoidance cannot suppress the
signal. Proposals change the committed mode map only via a PR — the kit
proposes, the human disposes; there is no automatic escalation.

### §8.2 Ratchet-down (propose quieter), and the ledger

Decline events live in a **git-ignored local gate ledger**
(`.claude/scratch/gate-ledger.md`, append-only machine lines:
`2026-07-06 PR#12 security_review declined`). Personal fatigue is personal —
counters are per-clone; the committed mode map is team policy and changes
only by PR. Rules: 5 declines spanning ≥3 distinct days → propose
`suggest-less-often` (natural-moments only) first; only a further streak
proposes `off`. A gate with `ci_job != none` can **never** be proposed `off`.
An accept resets the decline streak.

### §8.3 CI ratchet job

`ci.template.yml` gains a `ratchet` job: coverage (and perf when enabled)
compared against the baseline **in CI — the authoritative copy**. Mechanism
(one, not two): on merge to trunk, the job updates the baseline and pushes
(`permissions: contents: write`, a `paths-ignore` guard against loops, and a
documented note: protected trunks need a bypass-granted workflow token or the
job falls back to opening a bot PR). Local coverage-ratchet / perf-budget
runs become **advisory previews** — their SKILL.md write-the-baseline steps
are demoted in the same release (v2.1 edit list).

## §9 Substrate ledger

`docs/SUBSTRATE.md` — one section per assumed dependency; `requires:` fields
and Build-first menu items link to it. Dialect decisions are part of the
spec:

| § | Substrate | Ships | Language/dialect |
|---|---|---|---|
| 1 | `invocation_log` | DDL + the **normative schema** (single timestamp column; cost-check / perf-budget / incident-capture edited to match) + call-recording middleware sketch | SQLite canonical, Postgres variant in the same file; middleware sketch Python (Tier 1) |
| 2 | Eval runner | minimal pytest conftest loading the fixture shape | Python (Tier 1); Node runner explicitly deferred to v2.2 |
| 3 | Alert transport | ~30-line webhook sender | bash + curl (works everywhere) |
| 4 | Scheduler | documentation only: scheduled CI workflow or claude-code-remote triggers; the phantom `/schedule` and `scripts/*.py` references are deleted | n/a |

## §10 Stack tiers & the Tier-0 contract

### §10.1 Tiers

| Tier | Stacks | Means |
|---|---|---|
| 0 | The kit's own machinery | bash + git only. Bash helper scripts allowed; Python forbidden. |
| 1 | Python (uv/ruff/mypy/pytest) | Presets, CI template, reference impls, behavioral tests — maintained |
| 2 | Node/TS (v2.2: `node-service` preset, Node CI template, pino/prettier recipes, TS reference impl pair) | Same bar as Tier 1 once shipped |
| 3 | Everything else | Profile-compatible: toggles + empty-string skips; you supply commands; README says exactly this. Go promotes to Tier 2 on demand via the port playbook. |

### §10.2 Tier-0 lands in v2.0, not last

The consent front door is worthless if it crashes on the non-Python user it
courts. **v2.0 ships `scripts/kit-config.sh get <dotted.key>`** (~40-line
bash reader honoring §10.3) and de-Pythons the paths init, kit-doctor, and
adopt-existing-project need. Remaining Python (config-consistency-checker,
dependency-auditor agents, kit-update internals) completes in v2.2.

### §10.3 kit.yaml parse contract

Every key the bash layer reads obeys: two-space indent, one `key: value` per
line, no flow style, no anchors, single-line double-quoted strings. Stated
normatively in PROFILE.md; kit-ci validates the shipped kit.yaml and presets
against it. This is what makes `gates.modes.<key>` grep-able from hooks.

## §11 Enforcement portability & worktree provisioning

1. **Portability (PT9).** The enforce class must not depend on the editor.
   The deterministic-protective gates ship as **git hook variants**
   (secret-scan-diff.sh already documents its pre-push install; the
   credential guard gains one), installed by init when the repo has
   non-Claude-Code contributors (an Act-1 question). Conventions surface in
   an `AGENTS.md` pointer so other tools' agents see the same rules. The
   split is stated in the README: Claude hooks = full experience; git hooks =
   the safety floor for everyone.
2. **Provisioning (PT5).** `parallel-work` gains a provisioning step (deps
   install, env-file linking, per-tree ports) and `require-worktree.sh`'s
   block message mentions it. This is a prerequisite for §6.2 Phase 1 running
   green inside fresh worktrees; it ships in the same release as any preset
   that defaults `worktree_isolation: enforce`.

## §12 Migration from v1 & doctrine reconciliation

### §12.1 Behavior migration

- No `modes:` block → strictness behaves per §4.3's maps, which preserve v1's
  actual semantics (hard-safety gates blocked at every v1 level — they still
  do). The claim "no behavior change until the block is written" holds
  **because of** the §4.3 invariants.
- The mode-map offer for existing installs routes through **`/kit-menu`**
  (not kit-update — kit-update manages files, not config; it explicitly
  excludes kit.yaml).
- **kit-update prerequisites (PT10):** v2.0-alpha ships the per-version
  **file-hash manifest** (`path → sha256`, recorded at install/update time)
  so SAFE/NEEDS-REVIEW classification is real; kit-update becomes
  declined-aware (§5). Without the manifest, the §3 metadata rollout is
  honestly NEEDS-REVIEW-noisy for customized repos — the manifest is why
  it's scheduled first.
- kit-doctor's §3 check warns (not fails) while the project's `kit_version`
  is below the first v2 version — a hardcoded threshold in the check.

### §12.2 Doctrine edits (same PR as the mode map, or the docs lie)

- README "What no other package bundles" #1 → "**Enforced where it's
  deterministic and catastrophic; consented-and-recorded everywhere else.**"
  Worktree isolation is no longer cited as an always-block example.
- README differentiator #3 → "LLM behavior is gated where you turn it on —
  and the llm-app preset turns it on by default."
- README core idea #8 → chains + enforce-class hooks, not the 1% rule.
- PROFILE.md strictness table → regenerated from §4.3 (single normative
  copy); the "security review always blocks at every level" sentence is
  removed here **and** in pre-pr's strictness note — security review is
  suggest-class (subagent cost) except under `production` strictness.
- `spec_drift` for this repo: `suggest` (the kit now has a spec — this file).

## §13 Rejected & deferred

- **All-advisory (no enforce class):** rejected — the persona tests showed
  the praised artifacts are the enforced ones.
- **Full non-engineer product (`solo` preset, plain-language everything):**
  deferred (PT11); §5 adapts register only.
- **Measured per-run pricing in menus:** deferred until the invocation_log
  substrate exists; cost classes only (§5).
- **State curation (PT8):** deferred — trigger-gated on an adopted repo
  crossing ~3 months of accumulated state; explicitly not dropped.
- **kit-update config migrations:** rejected in favor of `/kit-menu` (§12.1).

## §14 Rollout

1. **v2.0-alpha — metadata & manifest (no behavior change):** §3 frontmatter
   on all ~30 skills; `scripts/gen-catalog.sh` + README markers + kit-ci
   drift check; PT10 file-hash manifest; kit-doctor metadata + ci_job checks.
   (~36 files.)
2. **v2.0a — the mode map:** §4 (kit.yaml + 5 presets + PROFILE.md table);
   `scripts/kit-config.sh`; hook mode-awareness (§4.5); two-phase pre-pr +
   `gates.triggers:` (§6.1–6.2); unattended rule (§6.4); gate-ledger record
   format (§8.2 — defined now so v2.1 can count); **§12.2 doctrine edits in
   this same release**; Tier-0 de-Python of doctor/init/adopt paths (§10.2).
3. **v2.0b — consent & chaining:** init interview (§5) + install-time
   pruning + `/kit-menu` + `declined:` consumers + kit-update
   declined-awareness; §7 chaining rewrite of using-the-kit + the 30 `Next:`
   Output edits; git-hook variants + AGENTS.md pointer + worktree
   provisioning (§11).
4. **v2.1 — backstop & substrate:** CI ratchet job + coverage/perf advisory
   demotion (§8.3); ratchet-up/-down proposals (§8.1–8.2); SUBSTRATE.md +
   DDL + conftest + webhook sender + schema unification + phantom-reference
   deletion (§9).
5. **v2.2 — Tier 2:** Node/TS preset, CI template, reference impls, Node
   eval-runner story; remaining de-Python (agents, kit-update internals).

Each phase is independently shippable. v2.0 was split (a/b) because the
original single phase touched ~50 files — a big-bang release the kit's own
phased-rollout doctrine forbids.
