#!/bin/bash
# PostToolUse hook for Edit|Write — autoformats the file that was just edited.
#
# The formatter is per-extension below. Defaults assume a Python/ruff project
# (# kit.yaml → toolchain.format); add/swap cases for prettier, gofmt, rustfmt
# to match your stack — logging-init/bootstrap will remind you.
#
# Input contract: tool input JSON on stdin ({"tool_input":{"file_path":"..."}}),
# jq → sed fallback → legacy $CLAUDE_FILE_PATH. Formatting is best-effort and
# never blocks (always exits 0), but an unresolvable input is still reported —
# a formatter that silently stopped firing is how style drift sneaks back in.
#
# Install: reference from .claude/settings.json under
#   hooks.PostToolUse[matcher="Edit|Write"]. See settings.template.json.

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
    echo "autoformat hook: could not resolve file_path from hook input — nothing formatted. Run kit-doctor." >&2
    exit 0
fi
[[ ! -f "$file" ]] && exit 0

case "$file" in
    *.py)
        # kit.yaml → toolchain.format
        if command -v ruff >/dev/null 2>&1; then
            ruff check --fix --quiet "$file" 2>/dev/null
            ruff format --quiet "$file" 2>/dev/null
        fi
        ;;
    # *.ts|*.tsx|*.js|*.jsx|*.json|*.css)
    #     npx --no-install prettier --write "$file" 2>/dev/null ;;
    # *.go)
    #     gofmt -w "$file" 2>/dev/null ;;
    # *.rs)
    #     rustfmt "$file" 2>/dev/null ;;
esac
exit 0
