---
name: using-the-kit
description: The kit's dispatcher — consult this before starting any task and before responding. If there is even a 1% chance a kit skill or gate applies to what you are about to do, you MUST invoke it. Contains the trigger index and the red-flags table of rationalizations to reject.
---

# Using the Kit

The kit's gates only protect the repo if they actually fire. Every skill in the
kit exists because skipping it once cost a real project real money, a red CI
queue, or a silent production failure. This skill is the dispatcher that makes
sure the right one runs at the right moment.

## The 1% rule

**If you think there is even a 1% chance a kit skill applies to what you are
doing, you MUST invoke it.** This is not negotiable, and it is cheap: a skill
whose capability toggle is off in `.claude/kit.yaml` reports N/A in seconds.
Reporting N/A is fine. Skipping the check silently is not.

Check for applicable skills **before** acting — before writing code, before
running commands, and before answering, including before asking clarifying
questions. The trigger index below is the checklist.

## Priority order

When more than one skill applies, run them in this order:

1. **Isolation first** — if you are about to edit files and are not in a
   worktree, `parallel-work` comes before everything else. The hook will block
   you anyway; don't fight it.
2. **Gates before actions** — `pre-pr` before `gh pr create`, `migration-check`
   before a migration lands, `config-audit` before committing `.claude/` changes.
3. **Capture last** — `followup-tracking`, `compound-learnings`, `doc-sync`,
   and `session-handoff` run when the work is done, not before.

## Red flags — rationalizations to reject

If you catch yourself thinking any of these, stop: it is the signal that a
skill applies, not a reason to skip it.

| Rationalization | Reality |
|---|---|
| "This is just a small change" | Small changes skip gates; gates exist because small changes broke things. Run `pre-pr` anyway — most steps will be fast or N/A. |
| "I'll run the checks after I open the PR" | That is exactly the red-CI-on-arrival the kit exists to prevent. The gate runs **before** `gh pr create`. |
| "The user is in a hurry" | A blocked queue or a leaked secret costs more time than any gate. Speed is not a reason to skip; it is a reason to run the gate early. |
| "This migration is obviously safe" | `migration-check` exists because "obviously safe" migrations dropped columns. Two minutes of checking beats an irreversible op on the primary. |
| "I'll remember this deferred decision" | You won't; the session ends. `followup-tracking` — 90 seconds. |
| "This debugging insight is too specific to write down" | Specific is exactly what `compound-learnings` wants. The next agent hits the same wall without it. |
| "The capability is probably off for this repo" | Then the skill reports N/A in seconds. Check `.claude/kit.yaml`; don't guess. |
| "I only changed a prompt string, not code" | Prompt changes are behavior changes. `prompt-regression` gates them for exactly this reason. |
| "I'm just editing config, not code" | `.claude/` config **is** the attack surface. `config-audit` before committing changes to it. |

## Trigger index

| The moment | Skill / agent to invoke |
|---|---|
| Starting any stream of work that edits files | `parallel-work` — get a worktree; never work on `main` |
| About to run `gh pr create` | `pre-pr` — the full local gate |
| Just opened or pushed to a PR | `ci-watch` — watch CI to green, fix failures |
| Change adds/edits a DB migration | `migration-check` |
| Change touches a prompt template or model config | `prompt-regression` |
| Change touches auth, secrets, user input, or external calls | **security-reviewer** agent (via `pre-pr` step 5) |
| Change alters behavior described in docs or the spec | `doc-sync` |
| Made a non-obvious design choice | `adr` |
| Finishing a unit of work with deferred decisions or accepted drift | `followup-tracking` |
| Solved a non-obvious problem (gnarly bug, tricky integration, workaround) | `compound-learnings` |
| Session ending mid-task, or handing off to another agent | `session-handoff` |
| A test failed, then passed with no code change | `flaky-triage` |
| Repo logs via print/console.log or ad-hoc logging, or `logging.initialized` is false | `logging-init` |
| Editing `.claude/settings.json`, hooks, CLAUDE.md, or MCP config | `config-audit` before committing |
| Writing or modifying a kit skill | `writing-kit-skills` |
| After install, profile edit, or a hook silently stopped firing | `kit-doctor` |
| Asked to check spend or before an expensive LLM run | `cost-check` |
| Multiple PRs open and someone must keep the queue moving | `pr-babysitter` / `branch-conflict-check` |
| New to this repo | **codebase-onboarder** agent |

Capability-gated skills (`migration-check`, `prompt-regression`, `perf-budget`,
`sync-health`, `cost-check`, …) read their toggle from `.claude/kit.yaml` and
report N/A when disabled — invoking them when in doubt is always safe.

## Output

No report block — this skill's output is the *other* skill you invoke. If you
checked the index and genuinely nothing applies, proceed; you do not need to
announce that.
