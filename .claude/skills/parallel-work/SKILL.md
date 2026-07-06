---
name: parallel-work
description: Isolate concurrent Claude sessions in git worktrees so multiple agents never cross wires on main — create, work, PR, and auto-clean per-branch worktrees
cost: cheap
protects: "Concurrent agents working in the same repo can't overwrite or corrupt each other's changes, because each stream of work gets its own isolated branch and worktree."
requires: nothing
gate_key: worktree_isolation
ci_job: none
---

# Parallel Work — Worktree Isolation for Concurrent Agents

Use this whenever more than one Claude instance may touch the repo at once, or
whenever you start a discrete unit of work that will become its own PR. The rule
is simple: **never edit source files on the `trunk_branch`.** Each stream of work
gets its own branch in its own git worktree, so two agents editing at the same
time can't corrupt each other's tree or produce a tangled trunk.

**Profile-driven.** The worktree root and trunk branch come from `.claude/kit.yaml`
(`worktree_dir`, default: `.claude/worktrees`; `trunk_branch`, default: `main`).
Update that file once to propagate the values everywhere.

> **Mode.** This gate runs per `gates.modes.worktree_isolation` in `.claude/kit.yaml`:
> `enforce` — run, block on failure; `suggest` — surface it at the natural
> moment with the `protects:` sentence and cost class above, run only on
> acceptance, and record accept/decline in the gate ledger
> (`.claude/scratch/gate-ledger.md`, SPEC.md §8.2) — never skip silently;
> `off` — not offered. Key absent → derive from `gates.strictness` per the
> table in `docs/PROFILE.md`. (SPEC.md §4.1, §4.4) The enforcing surface is
> the `require-worktree.sh` hook; at `suggest` the hook warns instead of
> blocking, and at `off` it is not installed (SPEC.md §4.5).

The `require-worktree.sh` PreToolUse hook enforces this — it blocks `Edit`/`Write`
on the `trunk_branch` in the primary worktree. If you hit that block, you're in the
wrong place; follow this skill.

## Workflow

### 1. Start an isolated worktree
Pick a branch name matching the change type (`feat/`, `fix/`, `docs/`, `chore/`):

```bash
# worktree_dir from kit.yaml (default: .claude/worktrees)
repo_root=$(git rev-parse --show-toplevel)
name=<short-kebab-slug>
git worktree add "$repo_root/.claude/worktrees/$name" -b feat/$name
```

From here on, **use absolute paths under that worktree** for every edit. Do not
`cd` narration into it and back — always address files as
`$repo_root/.claude/worktrees/$name/...` (substitute `worktree_dir` from
`.claude/kit.yaml` for `.claude/worktrees` if your project overrides it).

### 2. Background agents: lock the worktree
If you dispatch a long-running background agent to work in the tree, lock it so
the pruner won't reclaim it mid-flight:

```bash
# worktree_dir from kit.yaml (default: .claude/worktrees)
git worktree lock "$repo_root/.claude/worktrees/$name"
```

Unlock when the agent is done (`git worktree unlock <path>`).

### 3. Do the work, then gate it
Make your changes in the worktree. Before opening a PR, run the **pre-pr** skill
inside the worktree — it runs lint, types, and tests so CI doesn't fail on
arrival. Do not skip this; a red PR blocks the queue for every other agent.

### 4. Commit, push, open the PR
```bash
# worktree_dir from kit.yaml (default: .claude/worktrees)
git -C "$repo_root/.claude/worktrees/$name" add -A
git -C "$repo_root/.claude/worktrees/$name" commit -m "feat: ..."
git -C "$repo_root/.claude/worktrees/$name" push -u origin feat/$name
gh pr create --head feat/$name --fill
```

### 5. Cleanup is automatic
Once the PR merges, the `prune-merged-worktrees.sh` hook removes the worktree and
deletes the local branch — at session start and immediately after any
`gh pr merge`. You don't need to clean up by hand. It refuses to prune a tree
that is locked, dirty, recently active, or lacks a merged PR, so it's safe to
leave running.

## Coordination rules for a fleet of agents

- **One branch = one worktree = one concern.** Don't stack unrelated changes.
- **Exempt files can be edited on the `trunk_branch`** (the hook allows them):
  `CLAUDE.md`, `.claude/settings*`, `config/*.yaml`, `.gitignore`. A coordinating
  session may touch these directly; feature work should not.
- **Never force-push another agent's branch** and never merge a PR whose CI is
  red or whose worktree is still locked.
- **If two changes truly must land together**, say so in the PR body and merge in
  dependency order — don't co-edit one branch from two sessions.

## Output

When you finish, report:

```
## Worktree Summary
- Branch: feat/<name>
- Worktree: <worktree_dir>/<name>   (worktree_dir from .claude/kit.yaml)
- Pre-PR gate: PASS / FAIL — <detail>
- PR: #<n> (<url>)
- Cleanup: automatic on merge
```
