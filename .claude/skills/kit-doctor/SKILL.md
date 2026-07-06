---
name: kit-doctor
description: Verify an installed kit is correctly wired — checks toolchain commands, capability toggles, hook executability, settings references, and gh auth. Reports PASS/WARN/FAIL per check. Never modifies anything.
cost: cheap
protects: "Broken wiring in the installed kit — a hook that can't fire, a missing tool, a bad config — gets caught before it costs you a failed run."
requires: nothing
gate_key: none
ci_job: none
---

# Kit Doctor

Run this after adopting the kit, after any profile edit, or whenever a hook
silently stopped firing. Its job is to surface wiring problems before they cost
you a failed CI run or a swallowed exit code. It reads and checks only — it
never modifies files. (This checks that the wiring *works*; for whether the
config surface is *safe* — permissions, hooks, injection, secrets — run its
sibling, **config-audit**.)

## Checks

Work through every check below. Collect results as you go; emit the report at
the end in the fenced format shown. **Do not stop on the first failure** — run
all checks so the report is complete.

### 1. kit.yaml parses and has required keys

Read `.claude/kit.yaml` and confirm:

- The file is valid YAML (parse it; catch syntax errors).
- Required top-level keys are present: `kit_version`, `preset`, `trunk_branch`,
  `worktree_dir`, `toolchain`, `capabilities`.
- `kit_version` is a non-empty string.
- `preset` is one of: `library`, `service`, `llm-app`, `frontend`,
  `data-pipeline`, `custom`.

```bash
python3 -c "
import yaml, sys
with open('.claude/kit.yaml') as f:
    d = yaml.safe_load(f)
required = ['kit_version','preset','trunk_branch','worktree_dir','toolchain','capabilities']
missing = [k for k in required if k not in d]
if missing:
    print('MISSING:', missing); sys.exit(1)
valid_presets = {'library','service','llm-app','frontend','data-pipeline','custom'}
if d.get('preset') not in valid_presets:
    print('BAD PRESET:', d.get('preset')); sys.exit(1)
print('OK')
"
```

### 2. Toolchain commands resolve

For every key under `toolchain` whose value is a non-empty string, verify the
binary it invokes is on `PATH`. Use `command -v` on the first token of the
command string. Empty-string values are skipped (they mean "step disabled").

```bash
# kit.yaml → toolchain.*
python3 -c "
import yaml, shutil, sys
with open('.claude/kit.yaml') as f:
    tc = yaml.safe_load(f)['toolchain']
fails = []
for key, cmd in tc.items():
    if not cmd:
        continue
    binary = cmd.split()[0]
    if not shutil.which(binary):
        fails.append(f'{key}: binary not found: {binary}')
for f in fails:
    print('FAIL', f)
if fails:
    sys.exit(1)
print('OK')
"
```

Also run a dry/quick invocation for each non-empty toolchain command with
`--version` or `--help` if the binary supports it, to catch broken installs
(e.g., a `uv` wrapper that exists on PATH but fails at runtime). Use judgment —
if `--version` would trigger side effects, skip to the `command -v` result.

### 3. Capability toggles match reality

For each enabled capability, verify the required artifact exists:

| Capability | Check |
|---|---|
| `capabilities.migrations.enabled = true` | Binary of first token in `heads_cmd` is on PATH; `versions_glob` expands to at least one file (`find . -path "<glob>" | head -1`) |
| `capabilities.ui.enabled = true` | Binary of first token in `build_cmd` and `typecheck_cmd` are on PATH |
| `capabilities.llm.enabled = true` | `eval_dir` exists as a directory; `spend_table` is non-empty (warn if the DB file is also absent) |
| `capabilities.spec.file` non-empty | The named file exists at repo root |
| `capabilities.docs.enabled = true` | `docs.dir` exists as a directory |
| `capabilities.coverage.ratchet_enabled = true` | `baseline_file` exists (warn if absent — ratchet can't run without a baseline) |
| `logging.initialized = true` | `logging.library` is non-empty and appears in the project's dependencies/imports (WARN if not) |
| `logging.initialized = false` | WARN — structured logging not wired; run the `logging-init` skill |

A toggle set `true` with the required artifact missing is **WARN** (not FAIL)
unless the missing thing is a binary — a binary miss is **FAIL**.

### 4. Hooks are executable

Every `.sh` hook script referenced in `settings.json` must have the executable
bit set. Do **not** assume scripts live under `.claude/hooks/` — a repo may
wire hooks from `scripts/hooks/` or any other directory via `settings.json`.
Fall back to scanning `.claude/hooks/` for any scripts present but not wired.

```bash
python3 - <<'PY'
import json, os, glob, sys

not_exec = []
checked = set()

# Primary: follow settings.json to discover all wired hook scripts
try:
    data = json.load(open(".claude/settings.json"))
    for hook_list in data.get("hooks", {}).values():
        for entry in (hook_list if isinstance(hook_list, list) else []):
            for h in (entry.get("hooks", []) if isinstance(entry, dict) else []):
                cmd = h.get("command", "") if isinstance(h, dict) else ""
                for token in cmd.split():
                    if token.endswith(".sh"):
                        resolved = token.replace("$CLAUDE_PROJECT_DIR", ".") \
                                        .replace("${CLAUDE_PROJECT_DIR}", ".")
                        if resolved in checked:
                            continue
                        checked.add(resolved)
                        if not os.path.isfile(resolved):
                            not_exec.append(f"{resolved} (MISSING)")
                        elif not os.access(resolved, os.X_OK):
                            not_exec.append(resolved)
except FileNotFoundError:
    pass

# Secondary: also scan .claude/hooks/ for scripts present but not wired
for path in glob.glob(".claude/hooks/*.sh"):
    if path not in checked:
        checked.add(path)
        if not os.access(path, os.X_OK):
            not_exec.append(path)

for p in not_exec:
    print("FAIL not executable:", p)
if not not_exec:
    print("OK - all discovered hook scripts are executable")
PY
```

Any FAIL here means the hook fires (if wired in `settings.json`) but cannot
execute — it will silently never block. Fix with `chmod +x <path>`.

### 5. Hooks are referenced in settings.json

Read `.claude/settings.json`. For each `.sh` file under `.claude/hooks/`,
confirm the filename appears somewhere in `settings.json`. A hook that exists
on disk but has no entry in `settings.json` cannot fire.

```bash
python3 -c "
import json, os, sys
with open('.claude/settings.json') as f:
    raw = f.read()
hooks_dir = '.claude/hooks'
unreferenced = []
for name in os.listdir(hooks_dir):
    if name.endswith('.sh') and name not in raw:
        unreferenced.append(name)
for h in unreferenced:
    print('WARN unreferenced hook:', h)
"
```

Also confirm that each hook reference in `settings.json` uses
`$CLAUDE_PROJECT_DIR` for portability (not an absolute path). Absolute paths
are **WARN**.

### 6. Hook exit-code contract

For each hook script listed in `settings.json`, read its source and confirm
it does **not** end with `; true`, `|| true`, or `exit 0` unconditionally after
a failure-prone command. Swallowed exit codes mean the hook fires but never
blocks. Report each suspicious pattern as WARN with the line number.

Also check inline hook `command` strings in `settings.json`: flag any whose
**final top-level operator** is `|| true` or `; true` — this swallows the
hook's own exit code. Caveat: `|| true` used only to capture grep output into a
variable is a false positive; flag only when `|| true` or `; true` is the
terminal operation of the entire command string.

```bash
# Check hook script files discovered via settings.json + .claude/hooks/
python3 - <<'PY'
import json, os, glob

checked = set()
script_paths = []

try:
    data = json.load(open(".claude/settings.json"))
    for hook_list in data.get("hooks", {}).values():
        for entry in (hook_list if isinstance(hook_list, list) else []):
            for h in (entry.get("hooks", []) if isinstance(entry, dict) else []):
                cmd = h.get("command", "") if isinstance(h, dict) else ""
                for token in cmd.split():
                    if token.endswith(".sh"):
                        resolved = token.replace("$CLAUDE_PROJECT_DIR", ".") \
                                        .replace("${CLAUDE_PROJECT_DIR}", ".")
                        if resolved not in checked:
                            checked.add(resolved)
                            script_paths.append(resolved)
except FileNotFoundError:
    pass

for path in glob.glob(".claude/hooks/*.sh"):
    if path not in checked:
        script_paths.append(path)

found = False
for path in script_paths:
    if not os.path.isfile(path):
        continue
    with open(path) as fh:
        for i, line in enumerate(fh, 1):
            stripped = line.rstrip()
            if "; true" in stripped or "|| true" in stripped:
                print(f"WARN {path}:{i}: {stripped}")
                found = True
if not found:
    print("OK - no swallowed exit codes in hook scripts")
PY

# Also check inline command strings in settings.json for terminal exit suppression
python3 - <<'PY'
import json, re, sys

try:
    data = json.load(open(".claude/settings.json"))
except FileNotFoundError:
    sys.exit(0)

cmds = []
for hook_list in data.get("hooks", {}).values():
    for entry in (hook_list if isinstance(hook_list, list) else []):
        for h in (entry.get("hooks", []) if isinstance(entry, dict) else []):
            cmd = h.get("command", "") if isinstance(h, dict) else ""
            if cmd:
                cmds.append(cmd)

found = False
for cmd in cmds:
    # Flag when the FINAL top-level operation suppresses the exit code.
    if re.search(r'(\|\| *true|; *true)\s*$', cmd.rstrip()):
        print(f"WARN inline hook command ends with exit-suppressing operator:")
        print(f"  {cmd[:120]!r}")
        print(f"  (caveat: || true inside a variable assignment is a false positive — review manually)")
        found = True
if not found:
    print("OK - no exit-suppressing operators at end of inline hook commands")
PY
```

### 7. worktree_dir is gitignored

Read `.gitignore` (and `.git/info/exclude` if present) and confirm the value
of `worktree_dir` from `kit.yaml` is covered by a gitignore rule. Worktrees
committed to the repo are a mess.

```bash
python3 -c "
import yaml
with open('.claude/kit.yaml') as f:
    wd = yaml.safe_load(f)['worktree_dir']
import subprocess, sys
result = subprocess.run(['git','check-ignore','-q', wd], capture_output=True)
if result.returncode != 0:
    print('FAIL worktree_dir not gitignored:', wd)
    sys.exit(1)
print('OK')
"
```

### 8. CI workflow parses

```bash
python3 -c "
import yaml, glob, sys
files = glob.glob('.github/workflows/*.yml') + glob.glob('.github/workflows/*.yaml')
if not files:
    print('WARN no CI workflow files found')
    sys.exit(0)
errors = []
for f in files:
    try:
        yaml.safe_load(open(f))
    except yaml.YAMLError as e:
        errors.append(f'{f}: {e}')
for e in errors:
    print('FAIL', e)
if errors:
    sys.exit(1)
print('OK', len(files), 'workflow(s)')
"
```

### 9. gh auth (if any PR-based skill is in use)

Check whether any PR-based skill is referenced in `.claude/` (look for
strings like `gh pr create`, `pr-babysitter`, `branch-conflict-check`). If
found, verify `gh` is authed:

```bash
gh auth status 2>&1
```

Exit non-zero or "not logged in" output → FAIL. Absent `gh` binary → FAIL only
if PR skills are referenced.

### 10. settings.json is valid JSON

```bash
python3 -c "import json; json.load(open('.claude/settings.json')); print('OK')"
```

### 11. No stale progress ledgers

A ledger in `.claude/scratch/` marks an in-flight bootstrap / adoption /
kit-update run (see `docs/PROGRESS_LEDGER.md`). One older than 7 days means a
run was abandoned mid-way — **WARN** with the resume point (the first non-DONE
step), so it gets resumed or consciously deleted rather than forgotten.

```bash
find .claude/scratch -name '*-ledger.md' -mtime +7 2>/dev/null | while read -r f; do
  echo "WARN stale ledger: $f"
  grep -m1 -E '^\- \[ \]' "$f" || true
done
[ -d .claude/scratch ] || echo "OK - no scratch dir"
```

### 12. Skill metadata present and valid (SPEC.md §3)

Every `.claude/skills/*/SKILL.md` frontmatter (the block between the first two
`---` lines) must carry the full §3 field set — `name`, `description`, `cost`,
`protects`, `requires`, `gate_key`, `ci_job` — each single-line and non-empty.
`cost` must be one of `free`, `cheap`, `subagents`; `gate_key` must be a key in
the §4.2 set or the literal `none`. This is the metadata the init menu, the
README catalog, and checks 13–14 all read, so a malformed field silently breaks
generation downstream.

**Severity is version-gated (SPEC §12.1).** Read `kit_version` from
`.claude/kit.yaml`. While it is below the first v2 version — it starts with `0.`
or `1.` — the project predates the v2 metadata rollout, so any metadata problem
is **WARN**. At `2.x` or later it is **FAIL**. The threshold is hardcoded here.

```bash
GATE_SET="secrets_scan credential_files worktree_isolation lint_types_tests \
integration_tests migration_check coverage_ratchet perf_budget security_review \
test_gap docs_sync spec_drift prompt_regression branch_conflict \
observability_check flaky_triage sync_health ui_build build_artifact capture"

kit_version=$(sed -n 's/^kit_version:[[:space:]]*"\{0,1\}\([0-9][^" ]*\).*/\1/p' \
  .claude/kit.yaml | head -1)
case "$kit_version" in
  0.*|1.*) sev=WARN ;;   # pre-v2: metadata not rolled out yet
  *)       sev=FAIL ;;   # v2+: metadata is contractual
esac

problems=0
for f in .claude/skills/*/SKILL.md; do
  fm=$(awk 'NR==1 && /^---/{inside=1; next} /^---/{if(inside) exit} inside' "$f")
  for key in name description cost protects requires gate_key ci_job; do
    val=$(printf '%s\n' "$fm" | sed -n "s/^$key:[[:space:]]*//p" | head -1)
    [ -z "$val" ] && { echo "$sev $f: missing or empty field '$key'"; problems=$((problems+1)); }
  done
  cost=$(printf '%s\n' "$fm" | sed -n 's/^cost:[[:space:]]*//p' | head -1 | tr -d '"')
  case "$cost" in
    free|cheap|subagents|"") ;;
    *) echo "$sev $f: cost '$cost' not in {free,cheap,subagents}"; problems=$((problems+1)) ;;
  esac
  gk=$(printf '%s\n' "$fm" | sed -n 's/^gate_key:[[:space:]]*//p' | head -1 | tr -d '"')
  if [ -n "$gk" ] && [ "$gk" != none ]; then
    ok=0; for k in $GATE_SET; do [ "$k" = "$gk" ] && ok=1; done
    [ "$ok" -eq 0 ] && { echo "$sev $f: gate_key '$gk' not in the §4.2 set ∪ {none}"; problems=$((problems+1)); }
  fi
done
[ "$problems" -eq 0 ] && echo "OK - all skill metadata present and valid"
```

Emit the check at **WARN** or **FAIL** per the version gate above; **PASS** when
`problems` is zero.

### 13. ci_job consistency (SPEC.md §3, §2.3)

Two invariants tie skill metadata to CI. First, every `ci_job` value a skill
declares must name a real job. Collect each `ci_job` ≠ `none` (a value may be a
double-quoted comma-separated list like `"lint, typecheck, test"` — split on
commas and trim), and confirm each named job exists as a top-level `jobs:` child
in the installed CI workflows (`.github/workflows/*.yml`). When run inside the
source kit repo itself — detectable by the presence of `templates/ci.template.yml`
— also search that template, since it is the workflow projects actually copy.
A missing job is **FAIL**; no CI workflow present at all is **WARN**.

```bash
workflows=$(ls .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null)
template=""
[ -f templates/ci.template.yml ] && template="templates/ci.template.yml"  # source-kit clause

if [ -z "$workflows" ] && [ -z "$template" ]; then
  echo "WARN no CI workflow files found — ci_job consistency cannot be verified"
else
  job_src=$(cat $workflows $template 2>/dev/null)
  missing=0
  for f in .claude/skills/*/SKILL.md; do
    cj=$(sed -n 's/^ci_job:[[:space:]]*//p' "$f" | head -1 | tr -d '"')
    [ -z "$cj" ] || [ "$cj" = none ] && continue
    IFS=',' read -ra jobs <<< "$cj"
    for j in "${jobs[@]}"; do
      j=$(printf '%s' "$j" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
      [ -z "$j" ] && continue
      if ! printf '%s\n' "$job_src" | grep -qE "^  ${j}:"; then
        echo "FAIL $(basename "$(dirname "$f")"): ci_job '$j' not a job key in installed CI workflows or template"
        missing=$((missing+1))
      fi
    done
  done
  [ "$missing" -eq 0 ] && echo "OK - every ci_job value maps to a CI job key"
fi
```

Second, per §2.3/§4.4: any gate whose skill has `ci_job != none` is CI-backed
and must therefore be `enforce` in `gates.modes.<gate_key>` — **but only if a
`modes:` block exists**. Pre-§4 installs have no mode map yet; there is nothing
to check, so report `N/A (no mode map — strictness defaults apply per
docs/PROFILE.md)`.

```bash
if grep -qE '^  modes:' .claude/kit.yaml; then
  for f in .claude/skills/*/SKILL.md; do
    cj=$(sed -n 's/^ci_job:[[:space:]]*//p' "$f" | head -1 | tr -d '"')
    [ -z "$cj" ] || [ "$cj" = none ] && continue
    gk=$(sed -n 's/^gate_key:[[:space:]]*//p' "$f" | head -1 | tr -d '"')
    mode=$(sed -n "s/^    ${gk}:[[:space:]]*//p" .claude/kit.yaml | head -1)
    [ "$mode" != enforce ] && \
      echo "FAIL gate '$gk' (ci_job=$cj) is '$mode' in gates.modes — must be enforce (SPEC §2.3)"
  done
else
  echo "N/A (no mode map — strictness defaults apply per docs/PROFILE.md)"
fi
```

Missing job → **FAIL**; no workflow → **WARN**; a CI-backed gate not `enforce`
→ **FAIL**; no `modes:` block → the mode half is **N/A** (the ci_job-existence
half still runs).

### 14. Gate-key coverage (SPEC.md §4.2)

The §4.2 key set must be owned, exactly once, by exactly the surfaces that
implement it. Take the union of (a) every skill `gate_key` ≠ `none` and (b) the
static list of keys owned by non-skill surfaces — hooks own `secrets_scan`,
`credential_files`, `worktree_isolation`; agents own `security_review`,
`test_gap`, `spec_drift`; pre-pr steps own `integration_tests`, `ui_build`,
`build_artifact`. That union must equal the full §4.2 set exactly.

- A §4.2 key owned by nothing → **FAIL** ("gate key has no owner").
- A `gate_key` claimed by more than one skill → **FAIL**, EXCEPT `capture`
  (legitimately shared by followup-tracking + compound-learnings, §6.3) and
  `worktree_isolation` (owned by both the hook and the parallel-work skill by
  design).
- A key owned but absent from the §4.2 set → **FAIL** (a stray/renamed key).

```bash
NONSKILL="secrets_scan credential_files worktree_isolation security_review \
test_gap spec_drift integration_tests ui_build build_artifact"

skill_keys=$(for f in .claude/skills/*/SKILL.md; do
  gk=$(sed -n 's/^gate_key:[[:space:]]*//p' "$f" | head -1 | tr -d '"')
  [ -n "$gk" ] && [ "$gk" != none ] && echo "$gk"
done)

# Duplicate ownership across skills (capture + worktree_isolation exempt)
printf '%s\n' "$skill_keys" | sort | uniq -c | while read -r c k; do
  [ -z "$k" ] && continue
  if [ "$c" -gt 1 ]; then
    case "$k" in
      capture|worktree_isolation) ;;
      *) echo "FAIL gate_key '$k' claimed by $c skills (only capture and worktree_isolation may be shared)" ;;
    esac
  fi
done

union=$(printf '%s\n%s\n' "$skill_keys" "$(printf '%s\n' $NONSKILL)" | sed '/^$/d' | sort -u)
for k in $GATE_SET; do
  printf '%s\n' "$union" | grep -qx "$k" || echo "FAIL gate key '$k' has no owner"
done
printf '%s\n' "$union" | while read -r k; do
  printf '%s\n' $GATE_SET | grep -qx "$k" || echo "FAIL gate key '$k' owned but not in the §4.2 set"
done
```

(`$GATE_SET` is the list defined in check 12; if you run this check standalone,
redefine it.) **PASS** when the union equals the §4.2 set and no illegitimate
duplicate owner appears; any line above is a **FAIL**.

### 15. Kit manifest recorded (SPEC.md §12.1)

`.claude/kit-manifest.sha256` is the per-version file-hash manifest kit-update
reads to classify changes as SAFE vs NEEDS-REVIEW (PT10). It must exist and
every line must be `sha256sum` format — 64 hex chars, two spaces, a path.

```bash
manifest=.claude/kit-manifest.sha256
if [ ! -f "$manifest" ]; then
  echo "WARN no kit-manifest.sha256 — kit-update classification degrades to a git heuristic until a manifest is recorded — see SPEC.md §12.1"
else
  bad=$(grep -vnE '^[0-9a-f]{64}  .' "$manifest")
  if [ -n "$bad" ]; then
    echo "FAIL malformed manifest line(s):"; printf '%s\n' "$bad"
  else
    echo "OK - manifest present, all $(wc -l < "$manifest") line(s) well-formed"
  fi
fi
```

Missing manifest → **WARN** (kit-update still works, just falls back to a git
heuristic). Any malformed line → **FAIL**.

## Output

Emit exactly this fenced block with real results. Fill in the righthand column;
never leave a check blank.

```
## Kit Doctor Report

| Check | Result | Detail |
|---|---|---|
| kit.yaml parses + required keys | PASS/WARN/FAIL | — |
| Toolchain commands on PATH | PASS/WARN/FAIL | — |
| Capability toggles match reality | PASS/WARN/FAIL | — |
| Hooks executable | PASS/WARN/FAIL | — |
| Hooks referenced in settings.json | PASS/WARN/FAIL | — |
| Hook exit-code contract | PASS/WARN/FAIL | — |
| worktree_dir gitignored | PASS/WARN/FAIL | — |
| CI workflow parses | PASS/WARN/FAIL | — |
| gh auth | PASS/WARN/FAIL/N/A | — |
| settings.json valid JSON | PASS/WARN/FAIL | — |
| No stale progress ledgers | PASS/WARN | — |
| Skill metadata (§3) | PASS/WARN/FAIL | — |
| ci_job consistency | PASS/WARN/FAIL/N/A | — |
| Gate-key coverage (§4.2) | PASS/FAIL | — |
| Kit manifest recorded | PASS/WARN/FAIL | — |

Overall: PASS / WARN (N warnings, 0 failures) / FAIL (N failures)
```

**PASS** — all checks green.
**WARN** — at least one warning, no failures; the kit will mostly work but something may bite you.
**FAIL** — at least one failure; fix before relying on the kit.

Never modify any file. If a fix is obvious, describe it in the Detail column —
do not apply it.
