---
name: session-handoff
description: Write a tight durable state summary so a fresh session or another agent can resume the current task without re-deriving context
---

# Session Handoff

Run this when a long task is being interrupted — end of session, context
window pressure, handing off to a parallel agent, or stepping away mid-slice.
The goal is a **baton, not a report**: the minimum state a fresh agent needs
to pick up and run, without re-reading every file you already read. Keep it
under one screen. If it's longer than that, you've written a report; trim it.

> Write the handoff note to the project's scratchpad or a known slot in the
> repo (`docs/handoff.md` or `.claude/handoff.md`). The next session's first
> instruction should be: "read `.claude/handoff.md` before doing anything."
> Delete or overwrite the file when the task completes.

## Workflow

### 1. Capture the task identity

One sentence: what problem are we solving, and why does it matter now? Include
the slice name or issue number if applicable.

### 2. List what is done

Bullet each completed sub-task. Include commit SHAs or PR numbers so the next
agent can verify without re-running anything.

```bash
git log --oneline -10   # grab the relevant SHAs
git status --short      # confirm working tree state
```

### 3. Record what is in progress

Which sub-task is currently half-done? What file is it in? What is the
next line to write or the next test to pass?

### 4. Enumerate touched files and the active branch

```bash
git diff main...HEAD --name-only   # files changed from main
git branch --show-current           # active branch
git worktree list                   # if using worktrees
```

### 5. Summarize key decisions and their rationale

Two to five bullets, each following the pattern:
`<decision> — because <reason>`. Only include decisions that aren't obvious
from reading the code; things a fresh agent might reverse by mistake.

### 6. State the next concrete step

Be specific enough that the next agent can act without any inference:
file path, function name, what to add or change.

### 7. List blockers

Anything the next agent cannot proceed past without human input or an
external dependency resolving. If there are none, say so explicitly.

### 8. Write the file

Write the completed note to the handoff slot:

```bash
# project-local slot (preferred)
cat > .claude/handoff.md << 'EOF'
<handoff note>
EOF

# or scratchpad if the working tree is sensitive
cat > /tmp/claude-handoff.md << 'EOF'
<handoff note>
EOF
```

## Guardrails

- The handoff note is machine-readable state, not a progress narrative. Omit
  context the next agent can derive from reading the files you list.
- Never include secrets, tokens, or full file contents in the handoff note.
- If the task is complete, do not write a handoff note — close out the task
  and delete any existing handoff file instead.

## Output

```
## Handoff — <task name / slice ID> — <timestamp>

**Task:** <one sentence: what and why>
**Branch:** <branch-name> [worktree: <path if applicable>]

### Done
- <sub-task> — <commit SHA or PR #>
- <sub-task> — <commit SHA or PR #>

### In Progress
- <sub-task> — half-done in `<file:line>`, need to <specific next action>

### Key Decisions
- <decision> — because <reason>
- <decision> — because <reason>

### Next Step
`<file path>` → `<function/class>`: <exactly what to write or change>

### Blockers
- <blocker> — waiting on <who/what>
- none
```
