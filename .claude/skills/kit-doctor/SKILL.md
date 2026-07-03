---
name: kit-doctor
description: Verify an installed kit is correctly wired — checks toolchain commands, capability toggles, hook executability, settings references, and gh auth. Reports PASS/WARN/FAIL per check. Never modifies anything.
---

# Kit Doctor

Run this after adopting the kit, after any profile edit, or whenever a hook
silently stopped firing. Its job is to surface wiring problems before they cost
you a failed CI run or a swallowed exit code. It reads and checks only — it
never modifies files.

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

A toggle set `true` with the required artifact missing is **WARN** (not FAIL)
unless the missing thing is a binary — a binary miss is **FAIL**.

### 4. Hooks are executable

Every `.sh` file under `.claude/hooks/` must have the executable bit set.

```bash
find .claude/hooks -name '*.sh' ! -executable -print
```

Any file listed is a FAIL. This is the check that would have caught a hook
deployed without `chmod +x` and silently never firing.

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

```bash
grep -n '; true\||| true' .claude/hooks/*.sh 2>/dev/null
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

Overall: PASS / WARN (N warnings, 0 failures) / FAIL (N failures)
```

**PASS** — all checks green.
**WARN** — at least one warning, no failures; the kit will mostly work but something may bite you.
**FAIL** — at least one failure; fix before relying on the kit.

Never modify any file. If a fix is obvious, describe it in the Detail column —
do not apply it.
