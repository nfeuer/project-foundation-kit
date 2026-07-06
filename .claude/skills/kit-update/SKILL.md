---
name: kit-update
description: Propagate improvements from the source kit to a project that adopted it. Diffs kit-managed files, classifies changes as safe/needs-review/new, never clobbers local customizations silently, bumps kit_version after applying.
cost: cheap
protects: "Improvements from the source kit reach an adopted project without silently overwriting anything the team customized."
requires: "a source-kit checkout on disk"
gate_key: none
ci_job: none
---

# Kit Update

Run this when the source kit ships improvements you want to pull into a project
that already adopted it. It diffs kit-managed files one by one, classifies each
change, and applies only what is safe to apply without your input. Anything the
project customized comes to you for review. **Always dry-run first.**

**Progress ledger.** An apply run prompts per file and can be interrupted —
keep a ledger at `.claude/scratch/kit-update-ledger.md` (see
`docs/PROGRESS_LEDGER.md`): record each file's classification and, during
apply, each per-file decision (`applied` / `kept project version` / `skipped`)
as you go. On resume, do not re-ask for files already decided. Delete the
ledger after Step 7.

You need two paths:

- **Source kit** — the foundation-kit repo (default: `~/project-foundation-kit`
  or the path in `kit_source` if the project's `kit.yaml` sets it).
- **Project** — the repo you are updating (the current working directory).

## Workflow

### Step 0 — Locate both roots

```bash
# source kit root
KIT_ROOT="${KIT_SOURCE:-$HOME/project-foundation-kit}"

# project root (cwd)
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
```

Confirm both directories exist and both contain `.claude/kit.yaml`. If either
is missing, stop with a clear error — do not guess.

### Step 1 — Compare versions

```bash
python3 -c "
import yaml
kit = yaml.safe_load(open('$KIT_ROOT/.claude/kit.yaml'))['kit_version']
proj = yaml.safe_load(open('$PROJECT_ROOT/.claude/kit.yaml'))['kit_version']
print(f'Source kit: {kit}')
print(f'Project:    {proj}')
import packaging.version as pv
if pv.Version(proj) >= pv.Version(kit):
    print('Project is already at or ahead of source kit — nothing to do.')
    exit(0)
print(f'Update available: {proj} → {kit}')
"
```

If the project version is already at or ahead of the source kit version, report
that and stop. Do not proceed.

### Step 2 — Enumerate kit-managed files

Kit-managed files are everything under these paths in the source kit — the same
set the manifest (`scripts/gen-manifest.sh`) covers:

```
.claude/skills/*/SKILL.md
.claude/agents/*.md
.claude/hooks/*.sh
.claude/settings.template.json
```

Build the list (relative paths, one per line):

```bash
( cd "$KIT_ROOT" && {
    find .claude/skills -name 'SKILL.md'
    find .claude/agents -maxdepth 1 -name '*.md'
    find .claude/hooks  -name '*.sh'
    [ -f .claude/settings.template.json ] && echo .claude/settings.template.json
  } 2>/dev/null | sort )
```

Exclude `kit.yaml` itself — that is per-project configuration, not a kit-managed
template (per SPEC §12.1, kit-update manages files, not config; the mode map is
`/kit-menu`'s job). Note that `.claude/kit-manifest.sha256` is itself
kit-managed, but it is **not** diffed or prompted like a content file — it is
handled by Step 5's recording rule (copied wholesale to stamp the adopted
version). Do not add it to the per-file classification list in Step 3.

### Step 3 — Classify each file (dry-run)

Classification is **manifest-based**. The project carries a recorded
`.claude/kit-manifest.sha256` — the `sha256sum`-format list of kit-managed
paths and their hashes **as of the kit version the project last adopted**
(copied in at install/update time; see Step 5 and SPEC §12.1). That recorded
baseline is what makes the SAFE-vs-NEEDS-REVIEW split real: it is the third
point of a 3-way comparison between the project's current copy, the version the
project adopted, and the source kit HEAD.

For each kit-managed relative path `$REL`, gather three facts:

1. **source hash** — sha256 of `$KIT_ROOT/$REL` (the kit HEAD).
2. **project hash** — sha256 of `$PROJECT_ROOT/$REL` (absent if the file is
   missing in the project).
3. **recorded hash** — the hash for `$REL` in the project's recorded
   `.claude/kit-manifest.sha256` (absent if the path is not listed).

Then classify:

| Scenario | Classification | Action |
|---|---|---|
| project hash **==** source hash | SKIP | Up to date — project copy already equals kit HEAD |
| file **absent** in project | NEW | Offer to add it |
| project hash **== recorded** hash and source **differs** (project never touched it since adopting) | SAFE | Apply automatically (dry-run: show diff) |
| project hash **!= recorded** hash and source differs (locally modified) | NEEDS REVIEW | Show 3-way diff; ask before touching |
| `$REL` **not in** the recorded manifest (adopted pre-manifest, or a project-authored file shadowing a new kit path) and source differs | NEEDS REVIEW | Never SAFE — there is no baseline to prove the project copy is untouched |

The two rules that keep this honest: a file is **SAFE only** when the project's
current hash exactly matches what the manifest recorded (proving the project
never edited it), and a path **missing from the recorded manifest is never
SAFE** — without a recorded baseline we cannot distinguish an untouched adopted
file from a divergent local one, so it goes to review.

**Path mapping — settings.** The manifest tracks the source path
`.claude/settings.template.json`, but installs write it to the project as
`.claude/settings.json` (bootstrap copies it; adoption merges into an existing
one). For this one file, hash the project's `.claude/settings.json` and compare
it against the recorded hash of `.claude/settings.template.json` — and never
classify it SAFE: when the source template changed since the recorded version,
it is **always NEEDS REVIEW**. Settings are security-sensitive configuration
(hook wiring, permissions); changes are merged by hand and re-checked with
`config-audit`, never auto-applied. A project with no `.claude/settings.json`
at all is NEW.

```bash
# sha256 of a file, portable (Linux coreutils / macOS): prints just the hash
kit_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

MANIFEST="$PROJECT_ROOT/.claude/kit-manifest.sha256"

# recorded hash for an exact relative path from the project's manifest
recorded_hash() {
  # match the path column exactly (sha256sum format: "<hash><2 spaces><path>")
  awk -v p="$1" '$2 == p {print $1; exit}' "$MANIFEST"
}

# For each kit-managed relative path $REL:
SRC_HASH="$(kit_sha256 "$KIT_ROOT/$REL")"
if [ ! -e "$PROJECT_ROOT/$REL" ]; then
  echo "NEW"
else
  PROJ_HASH="$(kit_sha256 "$PROJECT_ROOT/$REL")"
  REC_HASH="$(recorded_hash "$REL")"
  if [ "$PROJ_HASH" = "$SRC_HASH" ]; then
    echo "SKIP"                       # already equals kit HEAD
  elif [ -z "$REC_HASH" ]; then
    echo "NEEDS REVIEW"               # no recorded baseline for this path
  elif [ "$PROJ_HASH" = "$REC_HASH" ]; then
    echo "SAFE"                       # untouched since adoption; source changed
  else
    echo "NEEDS REVIEW"               # locally modified
  fi
fi
```

For NEEDS REVIEW files, produce the 3-way diff for the report by showing the
source-vs-project diff (`diff "$PROJECT_ROOT/$REL" "$KIT_ROOT/$REL"`); note in
the prompt whether the divergence is from a local edit (recorded hash present
but mismatched) or from a missing baseline (path not in the manifest).

**Bash only — no Python here** (SPEC §10, Tier-0: kit machinery is bash + git).

#### Fallback — no recorded manifest (heuristic)

If the project has **no** `.claude/kit-manifest.sha256` (adopted before the
manifest shipped), fall back to the git-blame heuristic below, and **prefix the
report with a WARN**:

```
WARN: no .claude/kit-manifest.sha256 in this project — classification is a
git-blame heuristic and will over-report NEEDS REVIEW (e.g. after squash
merges). It becomes exact once a manifest is recorded on the next apply.
See SPEC §12.1 / follow-up PT10.
```

Heuristic: diff the project's copy against the source kit.

```bash
# For each kit-managed relative path $REL (fallback only):
diff "$KIT_ROOT/$REL" "$PROJECT_ROOT/$REL" > /dev/null 2>&1
# exit 0 → identical → SKIP
# exit 1 → differs → SAFE if project never touched it, else NEEDS REVIEW
# file missing in project → NEW
```

To distinguish SAFE from NEEDS REVIEW without a manifest: check
`git diff HEAD -- "$REL"` / git blame in the project. If git shows the
project-side file was modified after the kit was adopted (any local commit
changes it), classify as NEEDS REVIEW; otherwise SAFE. This is the heuristic the
manifest replaces — never trust it as strongly as a recorded hash.

### Step 4 — Print the dry-run report

Before applying anything, emit:

```
## Kit Update — Dry Run
Source kit: <version>
Project:    <version>

SAFE to apply (no local modifications):
  .claude/skills/pre-pr/SKILL.md
  .claude/hooks/secret-scan-diff.sh
  ...

NEEDS REVIEW (project has local modifications):
  .claude/skills/nightly-audit/SKILL.md
    --- source kit
    +++ project
    @@ ... @@
    <3-way diff excerpt>

NEW files (not present in project):
  .claude/skills/kit-doctor/SKILL.md
  .claude/skills/kit-update/SKILL.md
  ...

SKIP (already up to date):
  .claude/hooks/require-worktree.sh
  ...
```

**Stop here** unless the user explicitly asked for `--apply`. If dry-run only,
print the report and exit.

### Step 5 — Apply (only with explicit confirmation)

Do not apply without a clear instruction to proceed. When confirmed:

1. **SAFE files** — copy from source kit to project, overwriting. No prompt needed.
2. **NEEDS REVIEW files** — show the full diff and ask: "Apply source kit
   version, keep project version, or skip?" For each file, wait for the answer
   before moving to the next. Never clobber a customized file without a
   per-file explicit answer.
3. **NEW files** — ask: "Add this file?" For each new file, wait for confirmation.
4. **SKIP files** — do nothing.
5. **Record the manifest** — after all per-file decisions are made, copy the
   **source kit's** `.claude/kit-manifest.sha256` into the project at the same
   path, overwriting any previously recorded manifest. This stamps the version
   the project just adopted and is what makes the next update's Step 3
   classification exact (SPEC §12.1).

   ```bash
   cp "$KIT_ROOT/.claude/kit-manifest.sha256" \
      "$PROJECT_ROOT/.claude/kit-manifest.sha256"
   ```

   Note — this is by design, not a bug: any file where the user chose "keep
   project version" now hash-mismatches the freshly recorded manifest (the
   manifest lists the *new* source hash; the project kept the *old* content).
   On the next update that file correctly re-classifies **NEEDS REVIEW** rather
   than being silently overwritten as SAFE. Record the manifest even if some
   files were declined; a recorded baseline is always more accurate than none.

### Step 6 — Bump kit_version

After applying all changes (at least one SAFE or NEW file was written), update
`kit_version` in the project's `.claude/kit.yaml` to match the source kit:

```bash
python3 -c "
import yaml, re
with open('$PROJECT_ROOT/.claude/kit.yaml') as f:
    content = f.read()
with open('$KIT_ROOT/.claude/kit.yaml') as f:
    new_ver = yaml.safe_load(f)['kit_version']
updated = re.sub(
    r'(kit_version:\s*[\"\']).+?([\"\'])',
    lambda m: m.group(1) + new_ver + m.group(2),
    content,
    count=1,
)
if updated == content:
    print('ERROR: kit_version line not found/changed — version NOT bumped')
    raise SystemExit(1)
with open('$PROJECT_ROOT/.claude/kit.yaml', 'w') as f:
    f.write(updated)
print('kit_version bumped to', new_ver)
"
```

If no files were applied (all SAFE files declined, all NEEDS REVIEW skipped),
do not bump the version.

### Step 7 — Run kit-doctor

After applying, invoke the **kit-doctor** skill to confirm the updated install
is correctly wired. A kit-doctor FAIL after update means a file was applied
that broke a dependency — revert with `git restore` and investigate.

## Output

Emit one of these reports, depending on whether this was a dry run or a full
apply run:

**Dry run:**
```
## Kit Update — Dry Run
(report from Step 4)
Run with --apply to apply SAFE changes and prompt for NEEDS REVIEW and NEW.
```

**Apply run:**
```
## Kit Update — Applied
Source kit: <version>
Project:    <old version> → <new version>

Updated:
  .claude/skills/pre-pr/SKILL.md         SAFE applied
  .claude/hooks/secret-scan-diff.sh      SAFE applied

Reviewed:
  .claude/skills/nightly-audit/SKILL.md  kept project version (user choice)

Added:
  .claude/skills/kit-doctor/SKILL.md     added
  .claude/skills/kit-update/SKILL.md     added

Skipped (already up to date):
  .claude/hooks/require-worktree.sh

manifest: recorded (.claude/kit-manifest.sha256 → <new version>)
kit_version: <old> → <new>
Next: run kit-doctor to verify the updated install.
```

Never report a file as updated unless you actually wrote it. Never bump
`kit_version` unless at least one file was written.
