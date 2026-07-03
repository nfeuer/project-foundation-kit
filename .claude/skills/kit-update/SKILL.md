---
name: kit-update
description: Propagate improvements from the source kit to a project that adopted it. Diffs kit-managed files, classifies changes as safe/needs-review/new, never clobbers local customizations silently, bumps kit_version after applying.
---

# Kit Update

Run this when the source kit ships improvements you want to pull into a project
that already adopted it. It diffs kit-managed files one by one, classifies each
change, and applies only what is safe to apply without your input. Anything the
project customized comes to you for review. **Always dry-run first.**

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

Kit-managed files are everything under these paths in the source kit:

```
.claude/skills/*/SKILL.md
.claude/agents/*/AGENT.md      (if present)
.claude/hooks/*.sh
.claude/settings.template.json
```

Build the list:

```bash
find "$KIT_ROOT/.claude/skills" -name 'SKILL.md' \
  "$KIT_ROOT/.claude/hooks" -name '*.sh' \
  "$KIT_ROOT/.claude" -name 'settings.template.json' \
  2>/dev/null
```

Also include any `agents/` directory if it exists. Exclude `kit.yaml` itself —
that is per-project configuration, not a kit-managed template.

### Step 3 — Classify each file (dry-run)

For each kit file, compute its relative path (strip the `$KIT_ROOT` prefix) and
check whether the project has a copy at the same relative path:

| Scenario | Classification | Action |
|---|---|---|
| File exists in project and is **byte-for-byte identical to the previous kit version** (or identical to the current source) | SKIP | Nothing to do |
| File exists in project, project copy **differs from the previous kit version** but not from the source kit HEAD | SKIP | Already up to date |
| File exists in project, **project copy matches the previous kit version** (not locally modified) → source kit changed it | SAFE | Apply automatically (dry-run: show diff) |
| File exists in project, **project copy differs from both** the previous kit version and the source kit | NEEDS REVIEW | Show 3-way diff; ask before touching |
| File **does not exist in project** | NEW | Offer to add it |

To determine "locally modified" without storing the previous kit snapshot: diff
the project's copy against the source kit. If they differ, treat as NEEDS REVIEW.
If they are identical, treat as already up to date.

```bash
# For each kit-managed relative path $REL:
diff "$KIT_ROOT/$REL" "$PROJECT_ROOT/$REL" > /dev/null 2>&1
# exit 0 → identical → SKIP
# exit 1 → differs → SAFE if project never touched it, else NEEDS REVIEW
# file missing in project → NEW
```

To distinguish SAFE from NEEDS REVIEW: check git blame / `git diff HEAD --
"$REL"` in the project. If git shows the project-side file was modified after
the kit was adopted (any local commit changes it), classify as NEEDS REVIEW.
Otherwise SAFE.

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
    r'(kit_version:\s*[\"\']).+?([\"\']])',
    lambda m: m.group(1) + new_ver + m.group(2),
    content
)
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

kit_version: <old> → <new>
Next: run kit-doctor to verify the updated install.
```

Never report a file as updated unless you actually wrote it. Never bump
`kit_version` unless at least one file was written.
