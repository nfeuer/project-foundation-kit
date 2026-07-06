# Kit v2 — Consent-First Design Spec

**Status:** draft for review · **Supersedes:** the implicit v1 design (install
everything, enforce by default) · **Evidence base:** the 2026-07-06
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
   costs — once, at init, in plain language.
2. **Enforce only the deterministic and catastrophic.** A gate may block
   without asking only if it is (a) cheap, (b) deterministic (same diff → same
   verdict), and (c) protecting against an expensive-to-reverse failure.
   Today that set is: secrets scan, credential-file guard, migration heads,
   worktree isolation *where enabled*. Everything judgment-based or expensive
   defaults to suggestion.
3. **CI is law; local is advice.** The authoritative gate for anything
   ratchet- or baseline-shaped lives in CI, where it is race-free and
   unskippable. Local gates exist to make CI boring, not to substitute for it.
4. **Machinery agnostic, content tiered.** Everything needed to *operate* the
   kit (hooks, doctor, adopter, updater, init) runs on bash + git alone.
   Stack *content* (templates, CI jobs, language recipes) is explicitly
   tiered per §10 — deep where supported, honest where not.
5. **Claude is the operator; the human is the principal.** Machine-facing
   surfaces (skill bodies, reports) optimize for agent execution.
   Human-facing surfaces (init questions, block messages, WARN details) state
   outcomes and options in plain language, with the jargon available one level
   deeper.

## §3 Skill metadata (the priced catalog)

Every SKILL.md frontmatter gains three required fields:

```yaml
---
name: prompt-regression
description: <unchanged — the trigger sentence>
cost: subagents          # free | cheap | subagents
protects: "Prompt or model changes ship with a before/after eval score instead of a vibe."
requires: "eval fixtures + a runner (see §9 substrate ledger); capabilities.llm.enabled"
---
```

- `cost: free` — reads/writes a file, no model calls beyond the invoking turn.
- `cost: cheap` — runs project commands (lint, tests); bounded, no dispatches.
- `cost: subagents` — dispatches one or more subagents; the expensive class.
- `protects:` — one sentence, outcome language, readable by a non-engineer.
  This is the sentence the init menu shows.
- `requires:` — substrate or capability preconditions, or `nothing`.

`kit-doctor` gains a check: every skill has the three fields and `cost` is one
of the three values. The init menu (§5), the mode map defaults (§4), and the
README catalog are all *generated* from this metadata — one source of truth.

## §4 The gate mode map

`kit.yaml` replaces the single `gates.strictness` knob with a per-gate mode
map. Every gate-like skill runs in one of three modes:

```yaml
gates:
  # off     — not installed / never suggested
  # suggest — recommended at the natural moment; user (or agent policy) decides
  # enforce — blocks; failure stops the PR / the tool call
  modes:
    secrets_scan:      enforce     # deterministic + catastrophic (§2.2)
    credential_files:  enforce
    worktree_isolation: suggest    # enforce for teams; suggest for solo
    migration_check:   enforce     # when capabilities.migrations.enabled
    lint_types_tests:  enforce     # cheap + deterministic
    coverage_ratchet:  suggest    # authoritative copy runs in CI (§8)
    perf_budget:       off
    security_review:   suggest    # subagent dispatch — priced, not free
    test_gap:          suggest
    docs_sync:         suggest
    spec_drift:        off        # no spec file in this repo → off
    prompt_regression: suggest
  strictness: "standard"   # retained: prototype|standard|production now sets
                           # the DEFAULT mode map, which `modes:` overrides per-gate
```

Semantics:

- **enforce** — current v1 behavior: run, block on failure.
- **suggest** — the gate is *offered* at its natural moment (§6) with its
  `protects:` sentence and cost class; it runs only on acceptance. A declined
  suggestion is recorded in the run report (never silently skipped).
- **off** — not offered. `kit-doctor` reports off-gates in a one-line footer
  so they stay visible, not forgotten.

`strictness` maps to default mode maps: `prototype` (everything suggest except
secrets/credentials), `standard` (the map above), `production` (v1 behavior:
everything enforce). Explicit `modes:` entries always win. Migration: v1
installs without a `modes:` block behave exactly as their `strictness` level
did — no behavior change until the block is written.

## §5 The init interview (bootstrap v2)

`new-project-bootstrap` and `adopt-existing-project` share a three-act
front door. Act 1 and 2 are read-only.

**Act 1 — Learn.** The existing detection/audit machinery runs (stack probe,
CI probe, logging probe §1.8, migration probe). Output: an evidence table of
what the repo has and does.

**Act 2 — Explain.** Generate the menu from skill metadata (§3) + evidence:
each candidate capability rendered as *evidence → protection → cost*:

> ● **Migration safety** — you have alembic migrations. Blocks a destructive
> migration before it hits your database. Cost: free (runs a command).
> Recommended: **enforce**.
>
> ○ **Security review** — you make outbound HTTP calls. A reviewer agent
> audits auth/input-handling changes. Cost: ~1 subagent per flagged PR
> (≈ $0.20–0.80). Recommended: **suggest**.
>
> ✗ **Prompt regression** — requires eval fixtures you don't have yet
> (setup ≈ 2–4 days). Available later via `/kit-menu`.

Grouping: **Protect** (recommend-enforce set), **Guide** (suggest set),
**Build-first** (substrate-gated, shown with their prerequisite from
`requires:` — never installed as a dud). Three questions maximum beyond menu
choices, phrased for the audience the repo evidence implies (solo repo with no
CI ⇒ plain language register).

**Act 3 — Choose & record.** Only chosen skills are copied into `.claude/`
(install-time pruning replaces v1's `cp -r` — PT4). `kit.yaml` records the
mode map *and* the declined list with reasons:

```yaml
declined:
  eval_harness: "no fixtures yet — revisit when LLM behavior matters"
  worktree_isolation: "solo repo, single session"
```

The `declined:` block is what lets a later session (or `/kit-menu`, a new
lightweight skill that re-renders Act 2 against current evidence) offer
upgrades without re-pitching from zero, and what stops the dispatcher from
nagging about consciously-rejected gates.

## §6 Suggest-mode runtime UX

Suggestions surface at **natural moments**, not continuously:

| Moment | What is offered |
|---|---|
| Before `gh pr create` (pre-pr) | The gates whose triggers fired for THIS diff |
| After a unit of work completes | Capture skills: followups, compound-learnings, doc-sync |
| At session start on a repo with stale state | kit-doctor, resume-from-ledger |

`pre-pr` v2 becomes a **two-phase gate**: Phase 1 always runs the enforce-mode
set (cheap, deterministic). Phase 2 computes the *trigger set* from the diff
(auth files → security_review; migrations dir → migration_check; prompts/ →
prompt_regression; docs impact → docs_sync) and presents one menu:

> Enforced gates passed (lint, types, tests, secrets).
> Recommended for this diff: **security-review** (touched `auth/`), **doc-sync**
> (changed public API). Also available: coverage, test-gap.
> Run all / pick / skip (skips are recorded).

A docs-only or config-only diff therefore runs 3 steps, not 17. The 17-step
output block survives, but N/A rows are collapsed into a single summary line.

## §7 Chaining replaces the 1% rule

`using-the-kit` v2 drops the "1% chance → you MUST invoke" framing. In its
place, two mechanisms:

1. **Next-in-the-chain block.** Every skill's Output section ends with:
   ```
   Next: <skill> — <why it follows from what just happened> / none
   ```
   Standard chains: pre-pr → ci-watch → (merge) → compound-learnings;
   doc-sync → followup-tracking; incident → adr. The block is a suggestion
   with a reason, not an obligation.
2. **The trigger index stays** as the dispatcher's lookup table, but its
   contract softens to: *when a trigger matches, surface the suggestion with
   its `protects:` sentence; run enforce-mode gates without asking.* The
   red-flags table is retained only for enforce-mode gates (where "it's a
   small change" genuinely is a rationalization).

## §8 Earned enforcement & the CI backstop

- **Ratchet-up:** when a suggest-mode gate, having been accepted, produces a
  blocking-grade finding twice within a rolling window (tracked as a
  follow-ups entry, not hidden state), the next run proposes: *"security-review
  has caught 2 real issues; flip to enforce?"* Consent is still explicit;
  the kit proposes, the human disposes. There is no automatic mode escalation.
- **Ratchet-down:** a gate declined 5 consecutive times triggers the inverse
  proposal ("move to off and stop offering?") so suggestion fatigue has a
  sanctioned exit that keeps the decision visible.
- **CI backstop (PT6):** `ci.template.yml` gains a `ratchet` job — coverage
  (and perf, when enabled) compared against the baseline *in CI*. The CI copy
  is authoritative; local ratchet runs become advisory previews. Baseline
  files move to per-branch update-via-PR semantics: the ratchet job updates
  the baseline on merge to trunk (single writer), eliminating the concurrent
  local-ratchet merge conflicts.

## §9 Substrate ledger

The skills that assume unshipped infrastructure declare it (via `requires:`,
§3) and the kit ships a **substrate ledger** — `docs/SUBSTRATE.md` — with one
section per dependency: what it is, the schema/interface the kit expects, a
minimal reference implementation or an explicit "bring your own":

| Substrate | Consumers | v2 ships |
|---|---|---|
| `invocation_log` table | cost-check, perf-budget, incident-capture | DDL + one canonical schema (ends the column-name drift) + a call-recording middleware sketch |
| Eval runner | eval-harness, prompt-regression | a minimal pytest conftest that loads the fixture shape |
| Alert transport | fallback alerts, incident-capture, nightly-audit | a ~30-line webhook sender (Discord/Slack) |
| Scheduler | nightly-audit, pr-babysitter | documentation only: scheduled CI workflow or claude-code-remote triggers; the phantom `/schedule` reference is deleted |

Build-first menu items (§5) link to their ledger section.

## §10 Stack tiers

| Tier | Stacks | Means |
|---|---|---|
| 1 | Python (uv/ruff/mypy/pytest) | Presets, CI template, reference impls, behavioral tests — all maintained |
| 2 | Node/TS (next: `node-service` preset, Node CI template, pino/prettier recipes, one TS reference impl pair) | Same bar as Tier 1 once shipped |
| 3 | Everything else | Profile-compatible: toggles + empty-string skips work; you supply commands; README says exactly this |

Tier promotion requirements (the "stack port playbook", added to
`writing-kit-skills`): a preset, a CI template, logging + fallback reference
implementations, coverage/flaky adaptations, and behavioral-test coverage.
The kit's own machinery (hooks, doctor, adopter, updater, init) is Tier-0:
bash + git only, no Python (completes PT1).

## §11 Migration from v1

- v1 `gates.strictness` keeps working (§4); `kit-update` offers the mode map
  as a NEW file-less config change with the strictness-equivalent defaults.
- Installed-everything v1 repos: `/kit-menu` renders Act 2 against their
  evidence and offers to *remove* never-fired skills (dry-run list first).
- Metadata rollout: adding §3 frontmatter fields is a SAFE kit-update change
  (no body edits); kit-doctor's new check warns, not fails, for one minor
  version.

## §12 Rejected alternatives

- **All-advisory (pure Pathway C):** rejected — the persona tests showed the
  praised artifacts are the enforced ones; without the enforce class and the
  CI backstop the kit converges on a suggestion box.
- **Full plain-language rewrite of all surfaces:** rejected for v2 —
  human-facing surfaces adapt register via init evidence (§5); a full
  non-engineer product is out of scope until PT11's `solo` preset ships.
- **Per-skill pricing telemetry (measured $ per run):** deferred — cost
  *classes* (§3) are honest enough for consent; measured pricing needs the
  invocation_log substrate and can upgrade the menu later.

## §13 Rollout

1. **v2.0-alpha:** §3 metadata on all skills + generated README catalog +
   kit-doctor check. No behavior change.
2. **v2.0:** §4 mode map + §6 two-phase pre-pr + §7 chaining rewrite of
   using-the-kit + §5 init interview + install-time pruning.
3. **v2.1:** §8 earned enforcement + CI ratchet job + §9 substrate ledger
   (DDL, eval conftest, webhook sender).
4. **v2.2:** §10 Tier-2 Node/TS content; Tier-0 de-Pythoning completes.

Each phase is independently shippable and independently valuable, per the
kit's own phased-rollout doctrine.
