#!/bin/bash
# PreToolUse hook for Edit|Write — blocks edits on the trunk branch (main/master)
# in the primary worktree, forcing each Claude instance to work in its own
# isolated git worktree. This is what keeps two concurrent agents from crossing
# wires on the same files / muddying main.
#
# Exempt (safe to edit on main, since they rarely conflict and are often the
# thing a coordinating session needs to touch): CLAUDE.md, .claude/settings*,
# .claude/kit.yaml, config/*.yaml|*.yml, .gitignore. Tune the case-globs below.
#
# Mode-aware (SPEC.md §4.5): the block is governed by gates.modes.worktree_isolation
# in the repo's .claude/kit.yaml, read via the standalone grep/sed contract (§10.3)
# — NO dependency on scripts/kit-config.sh, so this keeps working when copied as a
# bare git hook. Semantics:
#   enforce → block edits on trunk outside a worktree (the behavior below);
#   suggest → allow the edit but print a one-line parallel-work warning to stderr;
#   off     → allow silently (§4.5: the hook shouldn't even be installed when off —
#             kit-doctor whitelists it; this runtime check is belt-and-braces).
# Fail-safe: kit.yaml missing, the key absent, or a malformed mode value all fall
# back to enforce — the hook degrades loudly toward blocking, never toward silence.
#
# Input contract: Claude Code passes the tool input as JSON on stdin —
# {"tool_input":{"file_path":"..."}}. Parsed with jq when available, a sed
# fallback otherwise, and the legacy $CLAUDE_FILE_PATH env var last. If no
# path can be resolved the hook allows the edit but says so on stderr — an
# Edit/Write payload always carries file_path, so silence here would mean the
# guard is off without anyone knowing.
#
# Install: reference this from .claude/settings.json under
#   hooks.PreToolUse[matcher="Edit|Write"]. See settings.template.json.
# Verified by the behavioral hook tests in .github/workflows/kit-ci.yml.

# --- Resolve the target file path from stdin JSON (jq → sed → legacy env) ---
payload=""
[[ ! -t 0 ]] && payload="$(cat 2>/dev/null)"

file=""
if [[ -n "$payload" ]]; then
    if command -v jq >/dev/null 2>&1; then
        file="$(printf '%s' "$payload" | jq -r '.tool_input.file_path // empty' 2>/dev/null)"
    fi
    if [[ -z "$file" ]]; then
        file="$(printf '%s' "$payload" \
            | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
            | head -1)"
    fi
fi
[[ -z "$file" ]] && file="${CLAUDE_FILE_PATH:-}"

if [[ -z "$file" ]]; then
    echo "require-worktree hook: could not resolve file_path from hook input — allowing this edit. The worktree guard may be miswired; run kit-doctor." >&2
    exit 0
fi

dir="$(dirname "$file")"
[[ ! -d "$dir" ]] && exit 0

# --- Exemptions: files that are safe to edit directly on the trunk branch ---
case "$file" in
    */CLAUDE.md|*/.claude/settings*|*/.claude/kit.yaml|*/config/*.yaml|*/config/*.yml|*/.gitignore)
        exit 0 ;;
esac

# --- Must be in a git repo on the trunk branch to be worth blocking ---
branch=$(git -C "$dir" branch --show-current 2>/dev/null) || exit 0
[[ "$branch" != "main" && "$branch" != "master" ]] && exit 0

# --- Already inside a linked worktree? Allow. ---
git_dir=$(cd "$dir" && cd "$(git rev-parse --git-dir 2>/dev/null)" 2>/dev/null && pwd -P)
git_common=$(cd "$dir" && cd "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null && pwd -P)
[[ -z "$git_dir" || -z "$git_common" ]] && exit 0

if [[ "$git_dir" != "$git_common" ]]; then
    # gitdir differs from common dir → a linked worktree (or a submodule).
    # Allow, unless it's a submodule of a superproject on main.
    superproject=$(git -C "$dir" rev-parse --show-superproject-working-tree 2>/dev/null)
    [[ -z "$superproject" ]] && exit 0
fi

# --- On the trunk branch in the primary worktree — mode decides the action ---
repo_root=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null)

# Read gates.modes.worktree_isolation standalone (§4.5/§10.3) — same one-line
# grep/sed style as the trunk_branch reader in secret-scan-diff.sh. The key sits
# at four-space indent under `gates:` → `  modes:`. Missing file, absent key, or a
# malformed value all fall back to enforce (fail-safe, per the header note).
mode="enforce"
if [[ -n "$repo_root" && -f "$repo_root/.claude/kit.yaml" ]]; then
    m=$(sed -n 's/^    worktree_isolation:[[:space:]]*//p' "$repo_root/.claude/kit.yaml" \
        | head -1 | sed 's/#.*//' | tr -d ' "'"'")
    case "$m" in
        enforce|suggest|off) mode="$m" ;;
        *)                   mode="enforce" ;;   # absent or malformed → enforce
    esac
fi

case "$mode" in
    off)
        # §4.5: an off gate should not be installed at all; allow silently if it is.
        exit 0 ;;
    suggest)
        echo "require-worktree hook [suggest mode]: editing '${file##*/}' on ${branch} outside a worktree — allowed, but concurrent parallel-work sessions can collide on shared files. Consider an isolated worktree first (worktree_isolation is set to 'suggest')." >&2
        exit 0 ;;
esac

# --- enforce: block ---
cat >&2 <<EOF
BLOCKED: Editing source files on ${branch} is disabled to prevent conflicts
between concurrent Claude sessions.

Create an isolated worktree before editing:
  git worktree add ${repo_root}/.claude/worktrees/<name> -b feat/<name>

Then use absolute paths under that worktree for all subsequent edits.
When finished: commit, push, run the pre-pr gate, and open a PR from the branch.

Exempt files (editable on ${branch}): CLAUDE.md, .claude/settings*,
.claude/kit.yaml, config/*.yaml, .gitignore
EOF
exit 2
