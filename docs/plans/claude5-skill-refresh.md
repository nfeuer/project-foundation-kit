# Plan: Refreshing the Kit's Skills for Claude Opus 5 & Sonnet 5

**Status:** proposed · **Scope:** the 30 skills under `.claude/skills/`, plus the
companion files that quote them (`CLAUDE.template.md`, `README.md`, `.claude/kit.yaml`,
`presets/*.yaml`, `docs/PROFILE.md`) · **Branch for implementation:** continue on
`claude/skills-opus-sonnet-5-b44lu0` or an equivalent working branch.

## Executive summary

The kit contains **zero hardcoded model IDs**, so this is not a string-swap migration.
It is a prompt-engineering refresh of ~4,900 lines of skill prose for how the Claude 5
generation actually behaves — plus one new capability (a model-routing convention) and
current model facts where skills discuss LLM cost.

A full multi-agent audit of all 30 skills produced **36 findings; 32 survived
adversarial validation** (4 rejected as churn). Result: **20 skills need edits, 10 need
none.** Only two findings are P1 (actively harmful on Claude 5), both the "1% rule"
doubt-threshold language in `using-the-kit` — which `SPEC.md` §7 ("Chaining replaces
the 1% rule") already designates for retirement. Everything else is P2/P3 tuning.

The four workstreams, in one sentence each:

1. **Retire doubt-threshold dispatch** ("even a 1% chance … you MUST") for plain
   condition-matching — Claude 5 models follow instructions literally, so
   emphasis-inflation written to overcome older models' reluctance now overtriggers.
2. **Standardize scope boundaries and review-recall language** — Opus 5 expands task
   scope unless bounded, and both models follow severity filters so literally that
   review steps silently lose recall.
3. **Add a model-routing convention** — code-writing steps run on `claude-opus-5` /
   `claude-sonnet-5`; planning and validation on `claude-fable-5`; mechanical checks
   on `claude-haiku-4-5` — expressed as profile keys, not hardcoded IDs.
4. **Refresh model facts** (IDs, pricing) in the LLM-ops skills, and calibrate
   deliverable length where skills author documents.

Execution follows the same model split the plan itself was built with: **Opus and
Sonnet agents write the edits; Fable agents only plan and validate.**

## How this plan was produced

A 14-agent workflow audited the corpus: 6 `claude-sonnet-5` analyzers (one per themed
batch of skills) applied a distilled Claude 5 behavioral rubric; 6 `claude-fable-5`
validators adversarially re-verified every finding against the actual files (verdicts:
19 CONFIRMED, 11 REVISED with corrected wording, 4 REJECTED, 1 missed-P2 recovered);
2 `claude-opus-5` drafters produced the conventions and wave structure; a final
`claude-fable-5` pass reconciled the drafts (one contradiction found and resolved —
see "Model-routing convention" below) and spot-verified every cross-file claim
(1%-rule references, `--check` flags on both regen scripts, SPEC §7).

## Current model facts (authoritative, July 2026)

| Model | ID | $/MTok in/out | Role in this kit |
|---|---|---|---|
| Claude Opus 5 | `claude-opus-5` | $5 / $25 | Code-writing: edits, fixes, migrations, generated artifacts |
| Claude Sonnet 5 | `claude-sonnet-5` | $3 / $15 (intro $2/$10 through 2026-08-31) | Code-writing, smaller diffs / cheaper runs; new tokenizer ~30% more tokens vs Sonnet 4.6 |
| Claude Haiku 4.5 | `claude-haiku-4-5` | $1 / $5 | Mechanical checks: greps, file existence, manifest diffs |
| Claude Fable 5 | `claude-fable-5` | $10 / $50 | Planning and validation: ADRs, handoffs, review agents, diff review |

Bare IDs only — never date-suffixed, never a retired `claude-3-*` ID.

## Behavioral deltas driving the changes

| # | Claude 5 behavior | Consequence for skill prose |
|---|---|---|
| 1 | Literal instruction following | "Even a 1% chance … you MUST" / "when in doubt, do X" overtriggers. True invariants (secrets, destructive ops, blocking gates) keep their MUST/NEVER. |
| 2 | Severity filters are followed literally in review tasks | "Only report high-severity" makes the model find bugs and then withhold them. Ask for every finding with confidence + severity; triage downstream. |
| 3 | Self-verification is built in (Opus 5) | "Double-check / re-verify / spawn a subagent to review your work" prose causes over-verification — delete it. Command-backed verification steps (run tests, diff a manifest) are workflow, not self-check — keep them. |
| 4 | Scope expansion (Opus 5) | Skills that only measure/report must say what they do *not* do. Existing "read-only" statements are good; standardize them — but never state a boundary broader than the truth. |
| 5 | Eager subagent delegation (Opus 5) | Fan-out guidance needs caps and criteria, not encouragement. |
| 6 | Native progress narration | Forced "summarize every N steps" scaffolding goes; durable progress *ledgers* (resume state) stay. |
| 8 | Longer written deliverables (Opus 5) | Document-producing skills (ADR, incident note, doc edits) get one length-calibration sentence. |
| 9 | Sonnet 5 tokenizer ≈ +30% tokens | Skill bodies cost more per invocation; trimming duplicated prose has real value. |

(Delta numbering matches the audit rubric; #7 and #10 produced no surviving findings.)

---

## Part 1 — Pattern-replacement table

Seven patterns generalize the 32 surviving findings. **Every diff hunk in the
implementation must cite a pattern row (PR-1…PR-7); an edit that maps to none has no
rubric basis and does not ship.**

| # | Old pattern | Replacement | Delta | Confirmed instances | Do **not** apply where |
|---|---|---|---|---|---|
| **PR-1** | Doubt-threshold dispatch: "if there is even a **1% chance** … you **MUST** invoke it", "not negotiable", "when in doubt, write it", "invoking them when in doubt is always safe" | State the matching condition plainly and name the deciding mechanism: "Scan the trigger index … if a row's condition matches what you are about to do, invoke that skill." Keep the anti-skip clause ("Reporting N/A is fine. Skipping the check silently is not.") — the fix removes the *threshold*, not the duty. | #1 | `using-the-kit` L3, L18–27, L84; `compound-learnings` L36–37; `writing-kit-skills` L99–100; `CLAUDE.template.md` L74–75; `README.md` L59, L141, L290 | Genuine invariants (secrets, destructive ops, "blocks the PR"). `SPEC.md` L19/L288/L417 *describe* the retirement — leave byte-stable. |
| **PR-2** | Unstated scope boundary in a skill that only measures/reports while its prose names a fix | One appended sentence, accurate to the skill's *sanctioned* writes: "This skill measures and reports; it does not tune the hot path itself." Carve out real writes explicitly. | #4 | 11 skills — see Wave 2 | Never claim a boundary broader than the truth (`sync-health` writes samples, alerts, a sentinel, an incident note — a blanket "read-only" there is a false invariant). |
| **PR-3** | Finding-suppressing filters on model-generated review output | Recall-first, triage-downstream: "report every finding with a confidence and severity rating — the accept/block decision happens in this step, not by the agent silently withholding lower-severity findings." | #2 | `pre-pr` L60–61, L66–68; `observability-check` (before `## Output`); `config-audit` L83–84 | Severity filters applied by a **tool** (`nightly-audit`'s `jq` HIGH/CRITICAL selection) — deterministic report contract, not model recall. |
| **PR-4** | Written deliverable with no length calibration | One calibration sentence at the point of authorship: "Keep each section tight — the value is in the decision and the rejected alternatives, not exhaustive prose." | #8 | `adr` §3; `doc-sync` §2; `incident-capture` L63–64 | `## Output` report templates — already length-bounded contracts. |
| **PR-5** | Model identifiers stale, absent, or invented where a skill discusses LLM cost/config | Current bare IDs routed through project aliases; prices as a sanity block that defers to the spend log's `cost_usd`. | new content | `eval-harness` L53–54; `prompt-regression` L82; `cost-check` (insert after L15); `nightly-audit` L105–106 | Don't invent routing the rubric doesn't state; don't hardcode a default model where the kit has aliases. |
| **PR-6** | Restated invariant or duplicated snippet in one body | Collapse to a cross-reference (keeping the bolded invariant), or merge duplicated heredocs into one copy-runnable script. | #9 | `flaky-triage` L133–134; `adopt-existing-project` §1.2 (duplicated hooks-walk heredocs) | Never drop the invariant itself; never change strings the `## Output` template quotes. |
| **PR-7** | Token-cost rationale predating the Sonnet 5 tokenizer | "…every line costs tokens, and Sonnet 5's tokenizer uses ~30% more tokens for the same text than Sonnet 4.6, so trimming redundant prose pays off more than it used to." | #9 | `writing-kit-skills` L122–123 | — |

## Part 2 — Amendments to `writing-kit-skills` (authoring guide)

Goal: a skill written *after* this sweep is Claude-5-native without the author
consulting the audit rubric. All amendments are additive or in-place; no section is
deleted (the only deletion is the phrase "1% rule" at L100).

- **A. §1 — model-fit note** (after "…must know exactly when to invoke it."):
  > Optionally state the skill's **model fit** in the intro paragraph: code-writing/
  > execution skills suit `models.code` / `models.code_light`; planning, validation,
  > or review skills suit `models.plan`. Write the role key, not a bare model ID —
  > the routing table lives in `using-the-kit` and the keys in `.claude/kit.yaml`
  > (see `docs/PROFILE.md`). One line of prose, not a frontmatter field.
- **B. §4 item 2 — boundary rule promoted to required + accuracy-bound**:
  > **State the boundary in the intro — one sentence.** Read-only skills say so
  > plainly ("It reads and checks only — it never modifies files"; `kit-doctor` is
  > canonical). Skills that write something narrow name the write and the non-write.
  > The boundary must be exhaustive-accurate — an over-broad "read-only" claim on a
  > skill that also writes a baseline file, a sentinel, or a chat alert is worse
  > than no boundary at all.
- **C. §5 L99–100 — de-reference the retired rule**:
  > - [ ] Add a row to the **trigger index** in `using-the-kit/SKILL.md` — the
  >   dispatcher only fires skills whose index row matches; no row, no trigger.
- **D. §6 — four new style rules** (appended):
  > - Trigger on a stated condition, not on doubt. Write "Run this when
  >   `<condition>`"; never "if there is even a chance…" or `You MUST` unless the
  >   rule is genuinely absolute (secrets, destructive ops, a blocking gate).
  > - Skills that request findings ask for **every** finding with confidence and
  >   severity, and triage downstream — never instruct the finder to pre-filter.
  > - Skills that produce a written document carry one length-calibration sentence.
  > - Do not tell the agent to double-check, re-verify, or spawn a subagent to
  >   review its own output — that is built in and only burns tokens. Command-backed
  >   verification steps are workflow; keep those. Fan-out guidance names a cap and
  >   a criterion: only genuinely independent, sizeable tracks; never to verify
  >   your own work.
- **E. §6 L122–123 — brevity rationale** strengthened per PR-7.
- **F. `## Output` template — two additive lines** (each with an explicit
  `none stated` form; no frontmatter key is added):
  ```
  - Boundary stated: <read-only | writes: <what> | none stated>
  - Model fit: <code | planning/validation | mechanical | none stated>
  ```

## Part 3 — Model-routing convention

> **Reconciled decision.** The two drafts this plan synthesizes disagreed: one
> proposed a profile-backed `models:` block in `kit.yaml`; the other kept routing as
> dispatcher prose with bare IDs and claimed "no new kit.yaml keys." This plan adopts
> the **profile-backed** form — it is the kit's own convention ("never hardcode a
> toolchain"; project-varying values live in the profile, skills cite dotted keys),
> and it makes retargeting the whole kit a one-line edit. Consequence: Wave 1 grows
> the full §5 registration duty (kit.yaml + all five presets + `docs/PROFILE.md` +
> one `kit-doctor` check), and Wave 7's checklist reflects that this key family
> already completed registration in Wave 1.

Three layers, no frontmatter key:

**`.claude/kit.yaml` (and all five `presets/*.yaml`, verbatim; `library.yaml` may set
`code: "claude-sonnet-5"` since its diffs are small):**

```yaml
# --- Model routing: which model executes which shape of step ---
# Skills name a role (code | plan | mechanical), never a bare model ID — same
# convention as `toolchain.test`. Empty string ("") = no preference; run the
# step on whatever model is already executing.
models:
  code:       "claude-opus-5"     # edits, fixes, migrations, generated artifacts
  code_light: "claude-sonnet-5"   # same work, smaller diffs / cheaper runs
  plan:       "claude-fable-5"    # planning, validation, review: adr, session-handoff, review agents
  mechanical: "claude-haiku-4-5"  # deterministic checks: greps, file existence, manifest diffs
  effort:
    code:       "high"            # low | medium | high | xhigh | max
    plan:       "high"
    mechanical: "low"
```

**`using-the-kit` — new `## Model routing` section (inserted before `## Output`):**

```markdown
## Model routing

Route by the shape of the step, not by which skill you are in. The profile's
`models.*` keys in `.claude/kit.yaml` hold the project's choices; the defaults
below apply when the block is absent or a value is empty.

| Step shape | Role key | Default | Effort |
|---|---|---|---|
| Writing or changing code — edits, fixes, migrations, generated artifacts | `models.code` | `claude-opus-5` (`models.code_light`, `claude-sonnet-5`, for small diffs) | high |
| Planning and validation — `adr`, `session-handoff`, spec and design decisions, and the review agents (`security-reviewer`, `test-gap-analyzer`, `observability-reviewer`, `spec-drift-checker`) | `models.plan` | `claude-fable-5` | high; xhigh for a full-diff security pass |
| Mechanical checks — file existence, greps, manifest diffs, `kit-doctor`'s wiring checks | `models.mechanical` | `claude-haiku-4-5`, or `claude-sonnet-5` at low effort | low |

This applies whenever you choose which agent or model runs a step: a subagent
spawn, a cron entry (`nightly-audit`, `pr-babysitter`), or a CI job. When you
do not control it, run the step where you are and say nothing. In skill bodies
write the role key, not a bare model ID; never a date-suffixed ID and never a
retired `claude-3-*` ID.
```

**`docs/PROFILE.md` — new item under "How skills consume the profile":**

> **Model roles.** `models.code`, `models.code_light`, `models.plan`, and
> `models.mechanical` name which model executes which shape of step, with per-role
> effort defaults under `models.effort`. Skills and the dispatcher cite the role key,
> never a literal model ID, so retargeting the kit is one edit here. Empty value =
> "no preference — run on the current model."

**Supporting check:** `kit-doctor` gains one check — every non-empty `models.*` value
is a current ID (`claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5`,
`claude-fable-5`); `claude-3-*` or date-suffixed → **FAIL**, unrecognized → **WARN**.
(`prompt-regression` gains the same retired-ID flag via PR-5; keep the two lists in
sync.)

---

## Part 4 — Phased execution plan

**Model assignment rule for every wave (matches how this kit's owner works): edits are
written by `claude-opus-5` (judgment-heavy rewrites) or `claude-sonnet-5` (mechanical
pattern application); `claude-fable-5` agents only plan and validate — they review
diffs, verify conventions held, and run the registration checklist. Fable never writes
the edits.**

Every edit applies a *validated* proposal: CONFIRMED verdicts as written, REVISED
verdicts in the validator's revised form, REJECTED findings never. Each wave is one
commit, so `git revert <wave-sha>` is the rollback unit.

### Wave 0 — Pre-flight baseline (no edits)

*Fable, effort low.* Confirm a clean tree; capture the green baseline
(`scripts/gen-manifest.sh --check` and `scripts/gen-catalog.sh --check` must both
exit 0 — if not, fix pre-existing drift before any Claude 5 work). Write an ADR (via
the `adr` skill — a planning artifact, correctly routed to Fable) recording the two
non-obvious decisions: retiring the 1% rule for the trigger-index contract, and the
profile-backed model-routing convention (rejected alternatives: keep the 1% rule; a
`model:` frontmatter field; dispatcher-prose-only routing).

### Wave 1 — Conventions layer (dispatch contract + authoring guide + routing) — **gates all later waves**

*Opus, effort high — two commits. Files: 14 · ~90 lines.*

**Commit 1a — retire the 1% rule (P1 + companions):**

| File | Change |
|---|---|
| `using-the-kit` L3 | Replace frontmatter description with the validator's listing-safe wording (no "below"; keeps the situation→trigger shape): "The kit's dispatcher — consult this before starting any task and before responding: scan its trigger index and invoke any skill whose row matches what you are about to do. Contains the trigger index and the red-flags table of rationalizations to reject." |
| `using-the-kit` L18–27 | Replace `## The 1% rule` with `## When to check`: "Scan the trigger index below before acting — before writing code, before running commands, and before responding, including before asking clarifying questions. If a row's condition matches what you are about to do, invoke that skill. The check is cheap: a skill whose capability toggle is off in `.claude/kit.yaml` reports N/A in seconds. Reporting N/A is fine. Skipping the check silently is not." |
| `using-the-kit` L84 | "report N/A when disabled — invoking a capability-gated skill costs only a quick N/A check when its toggle is off." |
| `writing-kit-skills` L99–100 | Amendment C (no row, no trigger). |
| `compound-learnings` L36–37 | Replace "When in doubt, write it" with condition-matching wording that keeps the anti-skip intent. |
| `CLAUDE.template.md` L74–75, `README.md` L59/L141/L290 | Companion sweep — retire 1%-rule wording, point at the trigger index. |

**Do not touch:** `SPEC.md` (§7 is the authority these edits catch up to) and the
historical `docs/changelog.md` entry mentioning the 1% rule.

**Commit 1b — model routing + authoring amendments:** the `models:` block in
`.claude/kit.yaml` + all five `presets/*.yaml`; `docs/PROFILE.md` item; the
`## Model routing` section in `using-the-kit`; `writing-kit-skills` amendments A, B,
D, E, F; one new `kit-doctor` check (registration duty for the new key family, per
§5 of `writing-kit-skills`).

**Verification (Fable, effort high):**
```bash
scripts/gen-catalog.sh --check   # WILL FAIL (description changed) → regen → re-check exit 0
scripts/gen-manifest.sh --check  # drift list must equal exactly the files above
grep -rn "1%" --include="*.md" . | grep -vE "SPEC.md|docs/changelog.md"   # expect: no hits
grep -rnE "claude-[a-z]+-[0-9]+-2026" .claude/ presets/                    # expect: none (no date suffixes)
```
Then invoke `config-audit` (skills and kit.yaml are agent-facing config) and read the
full diff. Reviewer explicitly confirms: the "before writing code / before running
commands / before responding, including before clarifying questions" condition
survived; the description reads correctly standalone in a listing; no capability
gate, profile tag, N/A form, or report-template line moved; presets ×5 and PROFILE.md
carry the block verbatim.

### Wave 2 — Scope-boundary standardization (PR-2, delta #4)

*Sonnet, effort medium (Opus at medium — or Sonnet at xhigh — for the three flagged
splices). Files: 11 · ~25 lines.* Append/splice one accurate boundary sentence per
skill: `migration-check` L20–21 (reports findings + mitigations; does not run
`alembic merge heads` or edit `downgrade()` bodies), `coverage-ratchet` L16–17 (no
source/test edits outside the sanctioned baseline write), `perf-budget` L19,
`observability-check` L20–21 (reports gaps; does not wire in logging or alerts),
`eval-harness` L22–23 ("authors, scores, and reports against fixtures" — not a
read-only claim; it writes fixtures), `prompt-regression` L77–78 (**`blocks the PR`**
must survive), `incident-capture` L89–90 (documents; does not revert the
primary-suspect commit), `new-project-bootstrap` L16.

Splice-sensitive (reviewer reads full paragraph context, not the hunk):
- ⚠️ `cost-check` L17–18 — revised text must end on the bare `It` so L19 flows.
- ⚠️ `nightly-audit` L16 — append and restore the trailing `This skill`.
- ⚠️ `sync-health` L68–69 — **accuracy risk**: say "never writes to primary or
  replica" and list the real side effects (log events, alert post, sentinel,
  incident note); do not claim an exhaustive artifact list (step 5 also writes
  `/tmp/*_sample.txt`). Keep the capability-gate sentence verbatim.

Verification (Fable, medium): manifest drift == exactly these 11 files; catalog check
still exits 0 (no frontmatter changed); every boundary claim verified *true* of the
skill as written.

### Wave 3 — Review-recall language (PR-3, delta #2)

*Sonnet, effort medium. Files: 3 · ~8 lines.* `pre-pr` L60–61 and L66–68: instruct
`test-gap-analyzer` and `security-reviewer` to report every finding with confidence +
severity; triage happens in the blocking-vs-follow-up split — the invariant "Any
finding blocks the PR until addressed or explicitly accepted" must not weaken.
`observability-check` (insert before `## Output`): report every gap with file/line;
downstream review triages. `config-audit` L83–84: "report ambiguous hits as
lower-confidence findings rather than omitting them" — **preserving** the trailing
"skim any skill added from outside the kit in full" clause.

Verification (Fable, medium): manifest drift == 3 files; no blocking rule softened;
no bash snippet or report template changed.

### Wave 4 — Current model facts (PR-5; depends on Wave 1)

*Sonnet, effort medium. Files: 4 · ~12 lines.* `eval-harness` L53–54: judge model
cited via the project's model aliases (e.g. `claude-sonnet-5`; never `claude-3-*`) —
do not hardcode a default or invent tier routing. `prompt-regression` L82: flag alias
changes resolving to a retired ID regardless of score delta; list the current set.
`cost-check`: insert the price sanity block **after L15, leaving L15 byte-stable**
(Opus 5 $5/$25 · Sonnet 5 $3/$15, intro $2/$10 through 2026-08-31 · Haiku 4.5 $1/$5 ·
Fable 5 $10/$50 — `cost_usd` in the spend table stays authoritative; update as
pricing changes). `nightly-audit` L105–106: fold the latest `cost-check`
GREEN/WARN/PAUSE verdict into the digest when `capabilities.llm.enabled` is true,
mirroring the existing `capabilities.replica.enabled` fold-in.

Verification (Fable, effort **high** — fact-checked, not just style-checked): every
price and ID diffed character-by-character against the model-facts table above;
`grep -rn "claude-3" .claude/skills/` hits only retired-ID *examples*.

### Wave 5 — Deliverable length + token trims (PR-4/PR-6/PR-7, deltas #8–#9)

*Sonnet, effort low. Files: 4 · ~8 lines.* `adr` §3: length calibration (a few
sentences per section; value is the decision and rejected alternatives). `doc-sync`
§2: "keep updates proportional to the change — amend the paragraph, not the page"
(leave "never hand-edit generated pages" untouched). `incident-capture` L63–64: note
calibration — facts and timeline, no speculative root-cause filler; the line must end
in a colon to lead into the bash block, and the 20-line cap is stated as imposed by
the commands below. `flaky-triage` L133–134: collapse the duplicated pass-rate-0
guardrail to a cross-reference to step 3, **keeping the bolded "Do not quarantine a
real failure."**

### Wave 6 — `adopt-existing-project` script consolidation (PR-6)

*Opus, effort xhigh. Files: 1 · ~70 lines → ~40 (net −30).* The only wave that
rewrites executable content, isolated last so a failure rolls back alone. Merge §1.2's
two python heredocs (both load `.claude/settings.json` and duplicate the same 7-line
`hooks.<Event>[].hooks[].command` walk at L72–79 and L113–120) into **one**
copy-runnable heredoc printing both sections: the per-`.sh`-token
executable/NOT EXECUTABLE/MISSING resolution, and the `PORTABILITY GAP` /
"no absolute paths in hook commands" block. Do **not** extract a shared named function
across two heredocs (breaks copy-runnability). The Output template's `Hooks wired` and
`Absolute paths in hook commands` lines stay byte-stable.

Verification (Fable, xhigh — behavioral equivalence): run the merged heredoc against
three fixtures (executable relative hook; missing/non-executable `.sh`; bare absolute
path) and confirm output matches the two originals. This is command-backed workflow
verification (delta #3's kept exception), not self-check prose.

### Wave 7 — Registration, versioning, release

*Sonnet executes (effort low); Fable validates (effort xhigh).*

1. Bump `kit_version` in `.claude/kit.yaml` — **once, here, for the whole sweep**
   (from `"2.0.0-alpha"`; exact target is the kit owner's call, e.g. `2.1.0-alpha`).
2. Regenerate in order: `scripts/gen-catalog.sh` then `scripts/gen-manifest.sh`;
   re-verify both with `--check` (exit 0).
3. Invoke `config-audit` (mandatory before committing `.claude/` changes) — confirm
   none of the new prose, especially the routing section and boundary sentences,
   reads as injection-shaped instruction.
4. Invoke `kit-doctor` — hooks, settings references, capability toggles, and the new
   `models.*` check all resolve after the Wave 6 script surgery.
5. `docs/changelog.md` entry naming: the retired 1% rule → trigger-index contract,
   the model-routing convention, standardized scope boundaries, refreshed model
   IDs/pricing; link the Wave 0 ADR.
6. Registration side-effects: the `models:` key family completed its full §5
   registration **in Wave 1** (kit.yaml + presets ×5 + PROFILE.md + kit-doctor).
   No new skill directories, hooks, or `pre-pr` steps exist; if any wave produced
   one, the full checklist applies and this wave is not done.
7. **Final review (Fable, xhigh):** read the entire branch diff against the audit
   corpus and confirm item by item — every CONFIRMED finding applied as written,
   every REVISED finding applied as revised, every REJECTED finding absent, no file
   changed that no wave named.

---

## Guardrails against churn

Byte-stable categories — edit only where a listed pattern row names the exact line:

1. Capability-gate sentences (`**Applies when** capabilities.<x>.enabled …`).
2. Profile-key tags (`# kit.yaml → toolchain.test`) and their literal defaults.
3. `## Output` report templates — line order, wording, `▢` glyphs, N/A forms; only
   the two additive `writing-kit-skills` lines are sanctioned.
4. Bash/`python3 -c`/heredoc snippets (sole sanctioned change: Wave 6, behavior-
   identical).
5. True invariants and honesty rules ("never check a box you didn't verify",
   blocking language, secrets/destructive-op gates).
6. Decision tables, the red-flags table, trigger-index rows (additions allowed;
   rewordings are churn).
7. Tool-derived severity contracts (`nightly-audit`'s `jq` HIGH/CRITICAL digest).
8. Command-backed verification steps (`new-project-bootstrap` L93–95,
   `compound-learnings` L75–76, `doc-sync` L23–24).
9. The frontmatter contract — no new keys anywhere.
10. Progress ledgers — state management, not narration.

**Do-not-resurrect list** (validated REJECTED findings; if one reappears in review,
cite this table):

| Skill | Struck proposal | Why struck |
|---|---|---|
| `new-project-bootstrap` L93–95 | Reword "Review the written file before continuing" | Criteria-backed manifest diff — delta #3's kept exception |
| `nightly-audit` L83 | Add MEDIUM/LOW counts to the digest | Mechanical `jq`/`pip-audit` filter inside a protected snippet |
| `compound-learnings` L75–76 | Trim "rather than assuming" | Validates a retrieved external doc, not the model's own output |
| `doc-sync` L23–24 | Soften "must"/"Always" on `--exclude-dir` | Command-correctness rule in a protected bash snippet |

## Rollback / abort criteria

Revert the wave commit immediately if: manifest drift appears in a file the wave did
not name; catalog check fails *after* a regen; `config-audit` returns a finding
attributable to the change; a protected category above changed without a wave item
naming it; a REJECTED finding was implemented or a REVISED one applied in its
original form; Wave 6's merged heredoc diverges from the originals on any fixture.

Dependencies: Waves 2, 3, 5, 6 are mutually independent. Wave 4 depends on Wave 1
(reverting Wave 1 requires reverting Wave 4). Wave 7 is regeneration — revert and
re-run the scripts, never hand-edit the manifest.

**Hard abort:** if Wave 1's dispatcher rewrite cannot preserve the "before writing
code / before running commands / before responding, including before clarifying
questions" condition without reintroducing doubt-threshold framing, stop and escalate
to the kit owner — losing that condition trades a P1 overtriggering problem for a P1
*under*-triggering one.

## Propagation to adopted projects

After Wave 7 lands on trunk, adopted projects pick the refresh up via `kit-update`
(version-stamp compare + manifest diff): uncustomized skills classify SAFE and apply
cleanly; locally-edited ones classify NEEDS-REVIEW with a diff. **Known gap to state
in the changelog:** `CLAUDE.template.md` is merged into a project's `CLAUDE.md` at
bootstrap, not tracked verbatim — adopters must hand-update the 1%-rule paragraph in
their own `CLAUDE.md`, or their agent keeps following a rule the dispatcher no longer
implements. Recommended adopter sequence: `kit-update` → `kit-doctor` →
`config-audit`.

## Out of scope — audited, no change

`branch-conflict-check` · `ci-watch` · `followup-tracking` · `kit-doctor`* ·
`kit-update` · `logging-init` · `parallel-work` · `pr-babysitter` · `release` ·
`session-handoff`

These returned a **no-change** verdict from the audit; the anti-churn rule keeps
their existing text byte-stable, and any manifest drift in this list is an abort
signal. (*`kit-doctor` gains one additive `models.*` check in Wave 1b as registration
duty for the new profile key — not a rubric-driven edit to its existing text.)

## Appendix — per-skill finding index

| Skill | Verdict | Findings (priority → pattern) | Wave |
|---|---|---|---|
| using-the-kit | needs-changes | P1→PR-1 ×2, P2→PR-1, P2→routing | 1 |
| writing-kit-skills | minor | P2→amendments ×2, P3→PR-7 (+recovered P2→PR-1 at L99) | 1 |
| compound-learnings | minor | P2→PR-1 | 1 |
| new-project-bootstrap | minor | P2→PR-2 | 2 |
| migration-check | minor | P2→PR-2 | 2 |
| coverage-ratchet | minor | P2→PR-2 | 2 |
| perf-budget | minor | P2→PR-2 | 2 |
| observability-check | needs-changes | P2→PR-2, P2→PR-3 | 2, 3 |
| eval-harness | minor | P2→PR-2, P3→PR-5 | 2, 4 |
| prompt-regression | minor | P2→PR-2, P3→PR-5 | 2, 4 |
| cost-check | minor | P2→PR-2 ⚠, P3→PR-5 | 2, 4 |
| nightly-audit | minor | P2→PR-2 ⚠, P3→PR-5 | 2, 4 |
| sync-health | minor | P3→PR-2 ⚠ (accuracy-bound) | 2 |
| incident-capture | minor | P2→PR-2, P3→PR-4 | 2, 5 |
| pre-pr | needs-changes | P2→PR-3 ×2 | 3 |
| config-audit | minor | P3→PR-3 | 3 |
| adr | minor | P2→PR-4 | 5 |
| doc-sync | minor | P3→PR-4 | 5 |
| flaky-triage | minor | P3→PR-6 | 5 |
| adopt-existing-project | minor | P3→PR-6 (heredoc merge) | 6 |

⚠ = splice-sensitive edit; reviewer reads full paragraph context.
