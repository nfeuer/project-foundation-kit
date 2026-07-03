#!/bin/bash
# Pre-commit / pre-PR hook — scans the staged diff or branch diff for secrets
# embedded in ordinary source files. The require-worktree guard blocks edits to
# known credential files; this catches the complementary failure mode: an API
# key pasted into a config module, a private key landed in a test helper, a
# token hardcoded in a fixture.
#
# Exit codes:
#   0  — clean
#   2  — secret pattern matched; commit BLOCKED
#
# Inline opt-out for intentional matches (test vectors, doc examples, stubs):
#   append  # pragma: allowlist secret  anywhere on the matching line.
#
# Exempt by default (never scanned — expected to contain key-shaped strings):
#   tests/fixtures/, /fixtures/, files whose path includes "example", "sample",
#   ".template.", or ".example.". Add project extras to EXEMPT_RE below.
#
# Install options:
#   git pre-commit hook  : cp this to .git/hooks/pre-commit && chmod +x
#   git pre-push hook    : cp to .git/hooks/pre-push         && chmod +x
#   Claude PreToolUse    : add to hooks.PreToolUse[matcher="Bash"] in
#                          .claude/settings.json — fires before each Bash call.
#   pre-pr gate          : call directly from the pre-pr skill step list.
#
# Note: entropy-based detection (high-entropy base64 blobs without a keyword
# anchor) is intentionally excluded here — pattern matching alone produces too
# many false positives. Add truffleHog or gitleaks to CI for that layer.

set -uo pipefail

# --- Diff scope: prefer staged changes (pre-commit); fall back to branch diff ---
if ! git diff --cached --quiet 2>/dev/null; then
    # Staged content present — pre-commit context
    diff_output=$(git diff --cached -U0 2>/dev/null) || exit 0
elif git rev-parse --verify main >/dev/null 2>&1; then
    # Nothing staged — scan the full branch against main (pre-push / manual run)
    diff_output=$(git diff main...HEAD -U0 2>/dev/null) || exit 0
else
    exit 0  # Can't determine a meaningful diff — let it through
fi

[[ -z "$diff_output" ]] && exit 0

# --- Exempt path patterns (awk ERE, matched against the repo-relative file path) ---
# Add project-specific path fragments separated by | to broaden exemptions.
EXEMPT_RE='tests/fixtures|/fixtures/|/examples?/|[Ee]xample|[Ss]ample|\.template\.|\.example\.'

# --- Extract added lines annotated with their source file path ---
# awk reads the diff stream, tracks the file from each "diff --git" header,
# and emits "filepath:content" for every added line that passes both the
# exempt-path filter and the inline opt-out check.
# The /^\+\+\+/ guard skips the +++ meta line that opens each file section.
added_lines=$(awk -v exempt_re="$EXEMPT_RE" '
    /^diff --git / {
        file = $4
        sub(/^b\//, "", file)
        skip = (file ~ exempt_re)
    }
    /^\+\+\+/ { next }
    /^\+/ {
        if (!skip) {
            content = substr($0, 2)
            if (content !~ /pragma: allowlist secret/) print file ":" content
        }
    }
' <<< "$diff_output")

[[ -z "$added_lines" ]] && exit 0

# --- Secret patterns (grep -E ERE, "LABEL|PATTERN" format) ---
# Keep these high-signal: a false positive trains engineers to ignore the scanner.
# Each label names what fired so the error message is immediately actionable.
PATTERNS=(
    "AWS access key ID|AKIA[0-9A-Z]{16}"
    "PEM private key header|-----BEGIN [A-Z ]*PRIVATE KEY"
    "Slack OAuth token|xox[baprs]-[0-9A-Za-z]{10,48}"
    "GitHub token|(ghp|ghs|gho|ghu|ghr)_[A-Za-z0-9]{36}"
    "Generic API key/token|(api[_-]?key|api[_-]?secret|access[_-]?token)[[:space:]]*[=:][[:space:]]*[A-Za-z0-9+/=_-]{20,}"
    "Generic secret/password|(secret|password|passwd)[[:space:]]*=[[:space:]]*[A-Za-z0-9+/=@!#%^&*_-]{16,}"
)

# --- Scan each pattern; collect all findings ---
findings=""
for entry in "${PATTERNS[@]}"; do
    label="${entry%%|*}"
    pattern="${entry#*|}"
    matches=$(grep -Ei "$pattern" <<< "$added_lines" 2>/dev/null || true)
    if [[ -n "$matches" ]]; then
        while IFS= read -r match; do
            findings+="  [$label] $match"$'\n'
        done <<< "$matches"
    fi
done

# Deduplicate (a line can match multiple patterns and would appear multiple times)
findings=$(printf '%s' "$findings" | sort -u)

# --- Block if anything found ---
if [[ -n "$findings" ]]; then
    cat >&2 <<EOF
BLOCKED: Possible secret(s) detected in diff.

${findings}
If a match is a false positive (test vector, doc example, intentional stub),
append to the end of the matching source line:
  # pragma: allowlist secret

Exempt paths: tests/fixtures/, /fixtures/, *example*, *sample*, *.template.*
For entropy-based scanning (base64 blobs), add truffleHog or gitleaks to CI.
EOF
    exit 2
fi

exit 0
