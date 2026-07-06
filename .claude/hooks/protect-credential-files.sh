#!/bin/bash
# PreToolUse hook for Edit|Write — refuses to edit secrets/credential files.
# Complements secret-scan-diff.sh (which catches secrets pasted into ordinary
# source files); this guards the credential files themselves.
#
# Input contract: tool input JSON on stdin ({"tool_input":{"file_path":"..."}}),
# parsed with jq when available, sed fallback, legacy $CLAUDE_FILE_PATH last.
# Unresolvable input allows the edit but reports it on stderr — never silently.
#
# Install: reference from .claude/settings.json under
#   hooks.PreToolUse[matcher="Edit|Write"]. See settings.template.json.
# Verified by the behavioral hook tests in .github/workflows/kit-ci.yml.

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
    echo "protect-credential-files hook: could not resolve file_path from hook input — allowing this edit. Run kit-doctor." >&2
    exit 0
fi

case "$file" in
    *.env|*.env.*|*credentials*.json|*token.json|*.pem|*.key|*secret*)
        echo "BLOCKED: refusing to edit a secrets/credential file: $file" >&2
        echo "Credential files are managed by humans, not agents. If this is a false positive, adjust the globs in .claude/hooks/protect-credential-files.sh." >&2
        exit 2 ;;
esac
exit 0
