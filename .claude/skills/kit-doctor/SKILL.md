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

This skill is **Tier-0** (SPEC.md §10.2): every check runs on bash + git +
coreutils — no `python3`. Profile values are read with
`scripts/kit-config.sh get <dotted.key> [default]` (the §10.3 parse contract;
exit 1 when a key is absent and no default is given). Each check that reads the
profile defines a one-line `kc` helper wrapping that script; when
`scripts/kit-config.sh` is not installed, `kc` falls back to the documented
one-line `sed` read of `.claude/kit.yaml` (reliable for top-level keys; nested
keys match on the leaf segment under the §10.3 one-key-per-line contract) and
check 1 surfaces a WARN telling you to install the kit's `scripts/` directory.
A full YAML/JSON *parse* (pyyaml) is deliberately **not** done here — the
authoritative parse of kit.yaml, the presets, and the CI workflow runs in
kit-ci, not in the doctor. Each snippet is standalone, so re-defining the `kc`
helper across checks is intentional.

### 1. kit.yaml parses and has required keys

Read `.claude/kit.yaml` and confirm:

- The file conforms to the §10.3 reader contract well enough for the bash layer
  — here "parses" means *readable by the Tier-0 reader*, not a full YAML parse
  (that runs in kit-ci; the pyyaml dependency is dropped from the doctor).
- Required top-level keys are present: `kit_version`, `preset`, `trunk_branch`,
  `worktree_dir`, `toolchain`, `capabilities` (the first four read as scalars
  via `kc`; `toolchain`/`capabilities` are mappings, so confirm the block
  header exists and probe one subkey of each).
- `kit_version` is a non-empty string.
- `preset` is one of: `library`, `service`, `llm-app`, `frontend`,
  `data-pipeline`, `custom`.

```bash
kc(){ if [ -x scripts/kit-config.sh ]; then scripts/kit-config.sh get "$@"; else k=${1##*.}; v=$(sed -n "s/^[[:space:]]*$k:[[:space:]]*//p" .claude/kit.yaml|head -1); v=${v%%#*}; v=$(printf '%s' "$v"|sed 's/[[:space:]]*$//;s/^"//;s/"$//'); [ -n "$v" ]&&{ printf '%s\n' "$v"; return 0; }||{ [ $# -ge 2 ]&&{ printf '%s\n' "$2"; return 0; }; return 1; }; fi; }

fail=0; warn=0
[ -f .claude/kit.yaml ] || { echo "FAIL .claude/kit.yaml missing"; fail=$((fail+1)); }
[ -x scripts/kit-config.sh ] || { echo "WARN scripts/kit-config.sh not found — using the sed fallback (top-level keys only); install the kit's scripts/ directory for full-fidelity profile reads"; warn=$((warn+1)); }

for k in kit_version preset trunk_branch worktree_dir; do
  if v=$(kc "$k"); then
    [ -n "$v" ] || { echo "FAIL required key empty: $k"; fail=$((fail+1)); }
  else
    echo "FAIL required key missing: $k"; fail=$((fail+1))
  fi
done
grep -qE '^toolchain:'    .claude/kit.yaml || { echo "FAIL required key missing: toolchain"; fail=$((fail+1)); }
grep -qE '^capabilities:' .claude/kit.yaml || { echo "FAIL required key missing: capabilities"; fail=$((fail+1)); }
kc toolchain.install >/dev/null 2>&1 || kc toolchain.test >/dev/null 2>&1 || { echo "WARN toolchain has no readable install/test subkey"; warn=$((warn+1)); }

preset=$(kc preset 2>/dev/null || true)
case "$preset" in
  library|service|llm-app|frontend|data-pipeline|custom) ;;
  *) echo "FAIL preset '$preset' not in {library,service,llm-app,frontend,data-pipeline,custom}"; fail=$((fail+1)) ;;
esac
[ "$fail" -eq 0 ] && [ "$warn" -eq 0 ] && echo "OK - kit.yaml readable, all required keys present, preset valid (full YAML parse is CI's job)"
```

### 2. Toolchain commands resolve

For every key under `toolchain` whose value is a non-empty string, verify the
binary it invokes is on `PATH`. Use `command -v` on the first token of the
command string. Empty-string values are skipped (they mean "step disabled").

```bash
kc(){ if [ -x scripts/kit-config.sh ]; then scripts/kit-config.sh get "$@"; else k=${1##*.}; v=$(sed -n "s/^[[:space:]]*$k:[[:space:]]*//p" .claude/kit.yaml|head -1); v=${v%%#*}; v=$(printf '%s' "$v"|sed 's/[[:space:]]*$//;s/^"//;s/"$//'); [ -n "$v" ]&&{ printf '%s\n' "$v"; return 0; }||{ [ $# -ge 2 ]&&{ printf '%s\n' "$2"; return 0; }; return 1; }; fi; }

fails=0
for k in lint format typecheck test test_integration build install; do
  v=$(kc "toolchain.$k" "")           # kit.yaml → toolchain.$k
  [ -n "$v" ] || continue             # empty string = step disabled, skip
  bin=${v%% *}                        # first token of the command
  command -v "$bin" >/dev/null 2>&1 || { echo "FAIL toolchain.$k: binary not found: $bin"; fails=$((fails+1)); }
done
[ "$fails" -eq 0 ] && echo "OK - all non-empty toolchain binaries resolve"
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

```bash
kc(){ if [ -x scripts/kit-config.sh ]; then scripts/kit-config.sh get "$@"; else k=${1##*.}; v=$(sed -n "s/^[[:space:]]*$k:[[:space:]]*//p" .claude/kit.yaml|head -1); v=${v%%#*}; v=$(printf '%s' "$v"|sed 's/[[:space:]]*$//;s/^"//;s/"$//'); [ -n "$v" ]&&{ printf '%s\n' "$v"; return 0; }||{ [ $# -ge 2 ]&&{ printf '%s\n' "$2"; return 0; }; return 1; }; fi; }
problems=0

if [ "$(kc capabilities.migrations.enabled false)" = true ]; then
  hb=$(kc capabilities.migrations.heads_cmd ""); hb=${hb%% *}
  [ -n "$hb" ] && { command -v "$hb" >/dev/null 2>&1 || { echo "FAIL migrations: heads_cmd binary not found: $hb"; problems=$((problems+1)); }; }
  vg=$(kc capabilities.migrations.versions_glob "")
  if [ -n "$vg" ]; then
    [ -n "$(find . -path "$vg" 2>/dev/null | head -1)" ] || { echo "WARN migrations: versions_glob matches no files: $vg"; problems=$((problems+1)); }
  fi
fi

if [ "$(kc capabilities.ui.enabled false)" = true ]; then
  for ck in build_cmd typecheck_cmd; do
    c=$(kc "capabilities.ui.$ck" ""); b=${c%% *}
    [ -n "$b" ] && { command -v "$b" >/dev/null 2>&1 || { echo "FAIL ui: $ck binary not found: $b"; problems=$((problems+1)); }; }
  done
fi

if [ "$(kc capabilities.llm.enabled false)" = true ]; then
  ed=$(kc capabilities.llm.eval_dir "")
  [ -n "$ed" ] && { [ -d "$ed" ] || { echo "WARN llm: eval_dir not a directory: $ed"; problems=$((problems+1)); }; }
  st=$(kc capabilities.llm.spend_table "")
  [ -n "$st" ] || { echo "WARN llm: spend_table is empty (warn also if the spend DB file is absent)"; problems=$((problems+1)); }
fi

sf=$(kc capabilities.spec.file "")
[ -n "$sf" ] && { [ -f "$sf" ] || { echo "WARN spec: file not found at repo root: $sf"; problems=$((problems+1)); }; }

if [ "$(kc capabilities.docs.enabled false)" = true ]; then
  dd=$(kc capabilities.docs.dir "")
  [ -n "$dd" ] && { [ -d "$dd" ] || { echo "WARN docs: dir not a directory: $dd"; problems=$((problems+1)); }; }
fi

if [ "$(kc capabilities.coverage.ratchet_enabled false)" = true ]; then
  bf=$(kc capabilities.coverage.baseline_file "")
  [ -n "$bf" ] && { [ -f "$bf" ] || { echo "WARN coverage: baseline_file absent — ratchet can't run without a baseline: $bf"; problems=$((problems+1)); }; }
fi

if [ "$(kc logging.initialized false)" = true ]; then
  lib=$(kc logging.library "")
  if [ -z "$lib" ]; then
    echo "WARN logging: initialized=true but logging.library is empty"; problems=$((problems+1))
  elif ! grep -rqiF "$lib" --include='*.py' --include='*.toml' --include='*.txt' --include='*.cfg' --include='*.lock' . 2>/dev/null; then
    echo "WARN logging: library '$lib' not found in project deps/imports"; problems=$((problems+1))
  fi
else
  echo "WARN logging: not initialized — run the logging-init skill"; problems=$((problems+1))
fi

[ "$problems" -eq 0 ] && echo "OK - enabled capabilities have their required artifacts"
```

### 4. Hooks are executable

Every `.sh` hook script referenced in `settings.json` must have the executable
bit set. Do **not** assume scripts live under `.claude/hooks/` — a repo may
wire hooks from `scripts/hooks/` or any other directory via `settings.json`.
Fall back to scanning `.claude/hooks/` for any scripts present but not wired.

`settings.json` is machine-written, so a token-level grep for `.sh` paths on the
`"command"` lines (with `$CLAUDE_PROJECT_DIR` substituted) is enough to discover
the wired scripts. A hand-mangled `settings.json` may need the **config-audit**
skill instead.

```bash
SETTINGS=.claude/settings.json
# Wired hook scripts: grep .sh paths out of the "command" lines only (skips the
# "//" comment prose), then resolve $CLAUDE_PROJECT_DIR to the repo root (".").
settings_hook_scripts(){ [ -f "$SETTINGS" ] || return 0; grep -E '"command"[[:space:]]*:' "$SETTINGS" | grep -oE '[^" ]*\.sh' | sed -e 's#\${CLAUDE_PROJECT_DIR}#.#g' -e 's#\$CLAUDE_PROJECT_DIR#.#g' | sort -u; }

n=0
# Primary: every hook wired in settings.json must be a present, executable file.
for s in $(settings_hook_scripts); do
  if [ ! -f "$s" ]; then echo "FAIL wired hook script missing: $s"; n=$((n+1))
  elif [ ! -x "$s" ]; then echo "FAIL not executable (chmod +x): $s"; n=$((n+1)); fi
done
# Secondary: scripts present under .claude/hooks/ must also carry the exec bit.
for s in .claude/hooks/*.sh; do
  [ -e "$s" ] || continue
  [ -x "$s" ] || { echo "FAIL not executable (chmod +x): $s"; n=$((n+1)); }
done
[ "$n" -eq 0 ] && echo "OK - all discovered hook scripts are executable"
```

Any FAIL here means the hook fires (if wired in `settings.json`) but cannot
execute — it will silently never block. Fix with `chmod +x <path>`.

### 5. Hooks are referenced in settings.json

Read `.claude/settings.json`. For each `.sh` file under `.claude/hooks/`,
confirm the filename appears somewhere in `settings.json`. A hook that exists
on disk but has no entry in `settings.json` cannot fire.

**Mode-map awareness (SPEC.md §4.5).** Three hooks carry an enforce-class gate:
`secret-scan-diff.sh` ↔ `secrets_scan`, `protect-credential-files.sh` ↔
`credential_files`, `require-worktree.sh` ↔ `worktree_isolation`. When a hook's
gate is `off` in `gates.modes`, §4.5 says the hook should **not** be installed,
so the unreferenced-hook scan whitelists it: present-but-unwired is expected
(one INFO line, not a WARN). But present-**and**-wired while the gate is `off`
is a **WARN** — it will warn-not-block at runtime, yet the profile says off.

```bash
kc(){ if [ -x scripts/kit-config.sh ]; then scripts/kit-config.sh get "$@"; else k=${1##*.}; v=$(sed -n "s/^[[:space:]]*$k:[[:space:]]*//p" .claude/kit.yaml|head -1); v=${v%%#*}; v=$(printf '%s' "$v"|sed 's/[[:space:]]*$//;s/^"//;s/"$//'); [ -n "$v" ]&&{ printf '%s\n' "$v"; return 0; }||{ [ $# -ge 2 ]&&{ printf '%s\n' "$2"; return 0; }; return 1; }; fi; }
SETTINGS=.claude/settings.json
settings_hook_scripts(){ [ -f "$SETTINGS" ] || return 0; grep -E '"command"[[:space:]]*:' "$SETTINGS" | grep -oE '[^" ]*\.sh' | sed -e 's#\${CLAUDE_PROJECT_DIR}#.#g' -e 's#\$CLAUDE_PROJECT_DIR#.#g' | sort -u; }
# hook filename -> the enforce-class gate_key it carries (SPEC §4.5).
hook_gate_key(){ case "$1" in
    require-worktree.sh)         echo worktree_isolation ;;
    secret-scan-diff.sh)         echo secrets_scan ;;
    protect-credential-files.sh) echo credential_files ;;
    *) echo "" ;; esac; }

n=0
if [ ! -f "$SETTINGS" ]; then
  echo "WARN no .claude/settings.json — cannot verify hook wiring (an installed kit copies it from settings.template.json; the source kit itself ships only the template)"
else
  raw=$(cat "$SETTINGS")
  for path in .claude/hooks/*.sh; do
    [ -e "$path" ] || continue
    name=$(basename "$path")
    gk=$(hook_gate_key "$name")
    mode=""; [ -n "$gk" ] && mode=$(kc "gates.modes.$gk" "")
    if printf '%s' "$raw" | grep -q "$name"; then referenced=1; else referenced=0; fi
    if [ "$mode" = off ]; then
      if [ "$referenced" -eq 1 ]; then
        echo "WARN $name is wired in settings.json but gates.modes.$gk = off — it warn-not-blocks at runtime while the profile says off (SPEC §4.5)"; n=$((n+1))
      else
        echo "INFO $name present but unwired — expected, gates.modes.$gk = off (SPEC §4.5)"
      fi
    elif [ "$referenced" -eq 0 ]; then
      echo "WARN unreferenced hook (on disk, no settings.json entry — cannot fire): $name"; n=$((n+1))
    fi
  done
  # Portability: each reference must use $CLAUDE_PROJECT_DIR, not an absolute path.
  for s in $(settings_hook_scripts); do
    case "$s" in /*) echo "WARN settings.json wires an absolute hook path (not portable): $s"; n=$((n+1)) ;; esac
  done
  [ "$n" -eq 0 ] && echo "OK - every on-disk hook is wired (or correctly off), all references portable"
fi
```

INFO lines above do not count toward WARN — an off-gate hook present but unwired
is a clean state. Absolute paths (references not using `$CLAUDE_PROJECT_DIR`) are
**WARN**.

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
SETTINGS=.claude/settings.json
settings_hook_scripts(){ [ -f "$SETTINGS" ] || return 0; grep -E '"command"[[:space:]]*:' "$SETTINGS" | grep -oE '[^" ]*\.sh' | sed -e 's#\${CLAUDE_PROJECT_DIR}#.#g' -e 's#\$CLAUDE_PROJECT_DIR#.#g' | sort -u; }

# Scan hook script files (settings-wired ∪ .claude/hooks/*.sh, deduped on path).
# Every line containing `|| true` / `; true` is flagged — same coarse match the
# prior check used; the variable-capture case is the documented false positive.
all_scripts=$( { settings_hook_scripts; ls .claude/hooks/*.sh 2>/dev/null; } | sed 's#^\./##' | sort -u )
found=0
for s in $all_scripts; do
  [ -f "$s" ] || continue
  hits=$(grep -nE '(\|\| *true|; *true)' "$s" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    printf '%s\n' "$hits" | while IFS= read -r h; do echo "WARN $s:$h"; done
    found=1
  fi
done
[ "$found" -eq 0 ] && echo "OK - no swallowed exit codes in hook scripts"

# Inline command strings: `"command"[^,}]*` grabs each command chunk; flag only
# when its FINAL top-level operator (allowing a trailing JSON quote) suppresses
# the exit code — a mid-command `|| true` variable capture is NOT flagged here.
inline=$(grep -oE '"command"[^,}]*' "$SETTINGS" 2>/dev/null || true)
if [ -n "$inline" ]; then
  printf '%s\n' "$inline" | while IFS= read -r c; do
    cc=$(printf '%s' "$c" | sed 's/[[:space:]]*$//; s/"[[:space:]]*$//; s/[[:space:]]*$//')
    case "$cc" in
      *'|| true'|*'; true')
        echo "WARN inline hook command ends with an exit-suppressing operator:"
        echo "  ${c}"
        echo "  (caveat: || true inside a variable assignment is a false positive — review manually)" ;;
    esac
  done
fi
```

### 7. worktree_dir is gitignored

Read `.gitignore` (and `.git/info/exclude` if present) and confirm the value
of `worktree_dir` from `kit.yaml` is covered by a gitignore rule. Worktrees
committed to the repo are a mess.

```bash
kc(){ if [ -x scripts/kit-config.sh ]; then scripts/kit-config.sh get "$@"; else k=${1##*.}; v=$(sed -n "s/^[[:space:]]*$k:[[:space:]]*//p" .claude/kit.yaml|head -1); v=${v%%#*}; v=$(printf '%s' "$v"|sed 's/[[:space:]]*$//;s/^"//;s/"$//'); [ -n "$v" ]&&{ printf '%s\n' "$v"; return 0; }||{ [ $# -ge 2 ]&&{ printf '%s\n' "$2"; return 0; }; return 1; }; fi; }

wd=$(kc worktree_dir "")
if [ -z "$wd" ]; then
  echo "FAIL worktree_dir not set in kit.yaml"
elif git check-ignore -q "$wd"; then
  echo "OK - worktree_dir gitignored: $wd"
else
  echo "FAIL worktree_dir not gitignored: $wd (add it to .gitignore)"
fi
```

### 8. CI workflow structural sanity

Without pyyaml this is a **structural** check, not a full parse: the file exists,
is non-empty, has a top-level `jobs:` block, and that block has at least one job
key. Authoritative YAML validation of the workflow lives in CI itself (kit-ci).
No workflow files at all → **WARN**.

```bash
files=$(ls .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null || true)
if [ -z "$files" ]; then
  echo "WARN no CI workflow files found"
else
  n=0; count=0
  for f in $files; do
    count=$((count+1))
    [ -s "$f" ] || { echo "FAIL empty workflow: $f"; n=$((n+1)); continue; }
    grep -qE '^jobs:' "$f" || { echo "FAIL no top-level 'jobs:' block: $f"; n=$((n+1)); continue; }
    if ! awk '/^jobs:[[:space:]]*$/{j=1;next} j&&/^  [A-Za-z0-9_.-]+:/{c++} END{exit(c>0?0:1)}' "$f"; then
      echo "FAIL 'jobs:' block has no job entries: $f"; n=$((n+1))
    fi
  done
  [ "$n" -eq 0 ] && echo "OK - $count workflow(s) structurally sane (authoritative YAML validation runs in CI itself)"
fi
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

Validate with the first JSON parser on `PATH` — `jq` first, then
`python3 -m json.tool` (used only if it exists; this skill never *requires*
python), and if neither is present fall back to a brace/bracket balance check
with an explicit note that it is not a real parse.

```bash
SETTINGS=.claude/settings.json
if [ ! -f "$SETTINGS" ]; then
  echo "WARN .claude/settings.json not found"
elif command -v jq >/dev/null 2>&1; then
  jq empty "$SETTINGS" >/dev/null 2>&1 && echo "OK - valid JSON (jq)" || echo "FAIL settings.json is not valid JSON (jq)"
elif command -v python3 >/dev/null 2>&1; then
  python3 -m json.tool "$SETTINGS" >/dev/null 2>&1 && echo "OK - valid JSON (python3 -m json.tool)" || echo "FAIL settings.json is not valid JSON (python3 -m json.tool)"
else
  o=$(tr -cd '{' < "$SETTINGS" | wc -c); c=$(tr -cd '}' < "$SETTINGS" | wc -c)
  b=$(tr -cd '[' < "$SETTINGS" | wc -c); d=$(tr -cd ']' < "$SETTINGS" | wc -c)
  if [ "$o" -eq "$c" ] && [ "$b" -eq "$d" ]; then
    echo "WARN no JSON validator on PATH (jq/python3) — brace/bracket balance is even but this is NOT a real parse; install jq for a real check"
  else
    echo "FAIL settings.json brace/bracket mismatch and no JSON validator on PATH: {=$o }=$c [=$b ]=$d"
  fi
fi
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
