# Follow-ups — project-foundation-kit

Deferred decisions, accepted drift, and cross-cutting follow-ups for the kit
itself. Format per `docs/followups.template.md`. IDs prefixed `PT` came out of
the 2026-07-06 five-persona friction test (solo TS hobbyist, brownfield team
lead, non-engineer, Go CLI dev, LLM startup team).

### PT1 — De-Python the kit's own machinery

- **Spec:** README "Adapting it — the profile"
- **Status:** open
- **Gap:** kit-doctor (8 of 11 checks), adopt-existing-project (4 heredocs),
  kit-update, config-consistency-checker, and dependency-auditor embed
  `python3 -c "import yaml"` snippets; PyYAML isn't stdlib, so the kit's own
  verification layer breaks first on Node/Go machines. Rewrite checks in pure
  bash/git where possible (`command -v`, `git check-ignore`, sed-based profile
  reads like secret-scan-diff.sh now uses); keep Python only where genuinely
  needed and gate it with a clear "requires python3+pyyaml" note.

### PT2 — The assumed LLM substrate is unnamed and unshipped

- **Spec:** README "Observability & evaluation" catalog group
- **Status:** open — partially addressed in v2.0-alpha: every skill now labels
  its preconditions up front (`requires:` frontmatter, SPEC.md §3); the
  substrate itself (DDL, eval conftest, webhook sender, schema unification)
  ships in v2.1 per SPEC.md §9
- **Gap:** Five skills query an `invocation_log` table nothing creates (and two
  disagree on its timestamp column name); eval-harness/prompt-regression assume
  a pytest eval runner that doesn't exist; `alerts.channel` has no transport
  implementation; all SQL is SQLite-dialect. Either ship the substrate (DDL +
  migration, call-recording middleware sketch, minimal eval conftest, webhook
  sender) or label each skill "requires substrate: X" up front. Also unify the
  invocation_log schema across cost-check / perf-budget / incident-capture.

### PT3 — Scheduled skills assume an always-on runner that is never named

- **Spec:** nightly-audit / pr-babysitter skills
- **Status:** open
- **Gap:** nightly-audit references a `/schedule` command and
  `scripts/build_audit_digest.py` / `scripts/check_spec_drift.py` that don't
  exist anywhere; pr-babysitter suggests `/loop` which requires a live session.
  Document the real options (scheduled CI workflow driving headless Claude,
  claude-code-remote triggers, or a dedicated runner) and remove the phantom
  references.

### PT4 — Ceremony doesn't scale: risk-tiered pre-pr + install-time pruning

- **Spec:** pre-pr skill; new-project-bootstrap step 4
- **Status:** open (design direction under discussion)
- **Gap:** pre-pr runs 17 steps with ≥4 subagent dispatches regardless of diff
  size — estimated $600–2,400/month at 10 PRs/day, and ~10 permanent N/A stamps
  on small projects. Bootstrap `cp -r`s all 30 skills + 8 agents regardless of
  preset. Wanted: a diff-risk tier (docs-only PR runs lint/secrets/tree only),
  `gates.strictness` extended to gate the expensive subagent dispatches, and
  bootstrap installing only the preset's skill subset.

### PT5 — Worktree provisioning is unaddressed

- **Spec:** parallel-work skill; require-worktree.sh block message
- **Status:** open
- **Gap:** A fresh worktree has no node_modules/.venv/.env/DB; pre-pr fails
  inside it until the user figures out per-tree setup. Add a provisioning step
  to parallel-work (install deps, link env files, per-tree ports) and mention
  it in the hook's block message.

### PT6 — Ratchet baselines race under concurrent agents; ratchet missing from CI

- **Spec:** coverage-ratchet / perf-budget skills; templates/ci.template.yml
- **Status:** open
- **Gap:** `.coverage-baseline` / `.perf-baseline.json` are single-line files
  two concurrent PRs will both update → guaranteed merge conflicts and TOCTOU
  gaps (a PR can land below a baseline ratcheted after its local gate ran).
  The CI template has no ratchet job, so the floor only exists locally. Add a
  CI-side ratchet job as the authoritative gate; treat local runs as advisory.

### PT7 — Stack tiers: presets and templates for Node and Go; `cli` preset

- **Spec:** presets/; templates/; new-project-bootstrap step 2 mapping table
- **Status:** open (design direction under discussion)
- **Gap:** No preset maps `go.mod` at all; a Node backend maps to `frontend`;
  the CI template and all code templates are Python-only; flaky-triage and
  coverage-ratchet embed pytest specifics. Decide tiering policy (see design
  discussion): Tier-1 Python (full), Tier-2 Node/TS, then Go — each with a real
  preset, CI template, and one reference logging/fallback implementation.

### PT8 — Accumulated state has no curation loop

- **Spec:** followup-tracking / compound-learnings / incident-capture skills
- **Status:** open (trigger-gated: revisit when any adopted repo passes ~3
  months of use)
- **Gap:** followups/solutions/incidents/fixtures grow monotonically; nothing
  re-validates, expires, or archives them, and agents read docs/solutions as
  priors — stale entries become confidently-wrong context. Add a curation pass
  (e.g., quarterly skill or a nightly-audit step that ages entries and proposes
  archival).

### PT9 — No tool-agnostic layer for mixed-editor teams

- **Spec:** README comparison section ("enforced, not suggested")
- **Status:** open
- **Gap:** All enforcement is Claude-Code-only; teammates on Cursor et al. are
  ungoverned, which breaks policy uniformity on shared repos. secret-scan
  already documents a git pre-push install path — surface that split explicitly
  (git-hook variants for the enforcement layer, AGENTS.md for conventions).

### PT10 — kit-update needs a real base-version manifest

- **Spec:** kit-update skill, step 3
- **Status:** closed (v2.0-alpha — `scripts/gen-manifest.sh` generates
  `.claude/kit-manifest.sha256` (kept current by kit-ci), install/adopt/update
  record it into the project, and kit-update step 3 classifies against the
  recorded baseline; settings.json gets an explicit never-SAFE mapping rule.
  SPEC.md §12.1)
- **Gap:** SAFE-vs-NEEDS-REVIEW classification degrades to a git-blame
  heuristic because no shipped-file-hash manifest exists; after squash merges,
  everything looks locally modified. Ship a per-version manifest
  (path → sha256) with the kit so 3-way classification is real.

### PT11 — Non-engineer surface: plain-language onboarding

- **Spec:** new-project-bootstrap; README intro
- **Status:** open (trigger-gated on the onboarding design direction)
- **Gap:** Every human-facing surface (questions, block messages, WARN
  details, README) assumes a mid-level engineer. A `solo` preset + a 5-question
  plain-language bootstrap interview + outcome-language hook messages would
  serve solo/non-engineer users; without them, that audience is out of scope
  and the README should say so.
