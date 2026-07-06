---
name: nightly-audit
description: Run the project's drift and health checks on a cron and post a compact morning digest to chat — turning "run it if you remember" into a standing signal.
cost: subagents
protects: "Docs, spec, dependencies, and follow-ups get checked every morning and only the problems worth acting on reach chat, instead of drift piling up unnoticed."
requires: "a scheduler (SUBSTRATE.md §4); alert transport (SUBSTRATE.md §3)"
gate_key: none
ci_job: none
---

# Nightly Audit

**Profile-driven.** Alert destination is `alerts.channel` / `alerts.target` in `.claude/kit.yaml`. Doc paths use `capabilities.docs.dir`. Spec-drift checks read `capabilities.spec.file` — if that key is empty, skip the spec-drift section entirely.

Drift accumulates in the gaps between work sessions: docs fall behind code, spec
sections go stale, follow-ups pile up, dependencies age into CVEs. This skill
wraps the project's existing health machinery (doc-sync, spec-drift, dependency
audit, follow-up count, CI status) into a single scheduled run that posts a
compact digest to chat each morning. A section that is all-green is omitted
entirely — the digest surfaces only actionable deltas, not a wall of checkmarks.
Use the `/schedule` skill to register the cron; `/loop` is an alternative for
polling during a dev session.

## Workflow

### 1. Register the scheduled run
Wire the agent to a daily cron with `/schedule`:

```
/schedule "nightly-audit" --cron "0 7 * * *"
```

The scheduled agent re-invokes this skill each morning. See `/schedule` for
secret injection (webhook URL, API keys) and retry behaviour. For a one-off
run or local testing, invoke the steps below directly.

### 2. Run doc-sync in audit mode
Identify stale narrative docs and broken internal links without writing anything.
Start from the branch diff, map each source change to its docs surface, and flag
pages that haven't been updated:

```bash
git diff main...HEAD --name-only
```

For each changed area check `docs/domain/`, `docs/workflows/`, `docs/operations/`
and `docs/changelog.md`. Run the `doc-sync` skill with `--dry-run` if available;
otherwise apply the same checklist manually and collect findings. Record stale page
names and broken link targets.

### 3. Check spec drift
**Skipped when `capabilities.spec.file` is empty in `kit.yaml`.** Otherwise, dispatch
the **spec-drift-checker** agent (or run the `spec-check` skill) against
`main` to surface spec sections that may no longer match the implementation:

```bash
# Example: project-local spec drift script
python scripts/check_spec_drift.py --output json 2>/dev/null
```

Collect: list of `§` sections suspected stale. See `doc-sync` for the update vs.
follow-up decision if a section needs work.

### 4. Run dependency and security audit
```bash
# Python
pip-audit --format json 2>/dev/null \
  | python -c "
import json, sys
vs = json.load(sys.stdin).get('vulnerabilities', [])
hi = [v for v in vs if v.get('fix_versions')]
print(f'{len(hi)} fixable ({len(vs)} total)')
for v in hi[:5]: print(f'  {v[\"name\"]} — {v[\"id\"]}')
"

# Node (swap pip-audit for npm audit when applicable)
npm audit --json 2>/dev/null \
  | jq -r '[.vulnerabilities | to_entries[]
     | select(.value.severity == "high" or .value.severity == "critical")]
     | "\(length) HIGH/CRITICAL"'
```

Report only HIGH and CRITICAL findings by package name. Strip CVE lists from
the digest — a link to the full `pip-audit` output is enough.

### 5. Count open follow-ups
```bash
# Count open entries in <docs.dir>/followups.md (capabilities.docs.dir from kit.yaml)
python -c "
import re, pathlib
text = pathlib.Path('docs/followups.md').read_text()
ids = re.findall(r'^### (\S+)', text, re.MULTILINE)
open_ids = [i for i in ids if 'RESOLVED' not in text[text.index(i):text.index(i)+300]]
print(len(open_ids))
" 2>/dev/null || grep -c '^### ' docs/followups.md 2>/dev/null || echo 0
```

Flag if the count grew since the previous digest (compare to a cached value or
yesterday's git blame on `docs/followups.md`). See the `followup-tracking` skill
for the entry format and stable ID convention.

Also report the **quarantined flaky-test** count and their age from
`flaky.registry` (default `docs/flaky-tests.md`) — a quarantine is a loan, so the
digest is where it's kept visible. Flag any quarantined test older than a
threshold or missing an owning follow-up. If `capabilities.replica.enabled` is
true, include the latest **sync-health** result (lag + parity) in the digest too.

### 6. Check CI status on main
```bash
gh run list --branch main --limit 10 \
  --json status,conclusion,workflowName \
  | jq -r '.[] | select(.conclusion != "success" and .conclusion != null)
           | "\(.workflowName): \(.conclusion)"'
```

Collect only workflows that are not green. Skip runs still in progress.

### 7. Assemble and post the digest
Build the digest, omit all-clear sections, and post via webhook. Silence is a
valid signal — do not post when there is nothing actionable:

```bash
# kit.yaml → alerts.channel (discord | slack | none) and alerts.target (channel/webhook var)
# Discord — swap URL and payload shape for Slack
payload=$(python scripts/build_audit_digest.py \
  --spec-drift   "$spec_findings"  \
  --dep-audit    "$dep_findings"   \
  --followup-count "$fu_count"     \
  --ci-failures  "$ci_failures")

[[ -z "$payload" ]] && exit 0   # nothing actionable, skip posting

curl -sX POST "$DISCORD_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d "$payload"
```

**Guardrail:** if any upstream check cannot run (Loki down, script error), post a
`#audit-failed` notice naming which checks were skipped, then exit non-zero so the
scheduler retries. Never silently omit a check — a missing section looks the same
as a green one.

## Output
```
## Nightly Audit — <YYYY-MM-DD>
Docs:         <N stale pages — list | clean>
Spec:         <N §sections drifting — list | clean>
Deps:         <N HIGH/CRITICAL — package names | clean>
Follow-ups:   <N open (+N since yesterday | unchanged)>
CI (main):    <workflow names red | all green>
---
Action items:
- <item>
(section omitted when nothing to act on; digest not posted if all sections omit)
```
