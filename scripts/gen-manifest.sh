#!/usr/bin/env bash
# gen-manifest.sh — write/verify the per-version kit file-hash manifest (PT10).
#
# SPEC citation: SPEC.md §12.1 — kit-update needs a "path → sha256" manifest
# recorded at install/update time so SAFE/NEEDS-REVIEW classification is real.
# Tier-0 per SPEC.md §10: bash + git + coreutils only; must run on macOS
# bash 3.2 (shasum) and Linux (sha256sum).
#
# Usage:
#   scripts/gen-manifest.sh           write .claude/kit-manifest.sha256
#   scripts/gen-manifest.sh --check   exit 1 if the committed manifest drifted
#
# Env: KIT_ROOT overrides the repo root (default: git rev-parse --show-toplevel).

set -euo pipefail

KIT_ROOT="${KIT_ROOT:-$(git rev-parse --show-toplevel)}"
cd "$KIT_ROOT"

MANIFEST=".claude/kit-manifest.sha256"

if command -v sha256sum >/dev/null 2>&1; then
    HASH="sha256sum"
elif command -v shasum >/dev/null 2>&1; then
    HASH="shasum -a 256"
else
    echo "gen-manifest: neither sha256sum nor shasum found on PATH" >&2
    exit 1
fi

TMP=$(mktemp "${TMPDIR:-/tmp}/gen-manifest.XXXXXX")
trap 'rm -f "$TMP"' EXIT

# The kit-managed set kit-update enumerates (SPEC.md §12.1). The manifest
# itself is never included. Paths are repo-root-relative, sorted LC_ALL=C.
# scripts/kit-config.sh ships to projects (bootstrap/adopt copy it so
# kit-doctor's bash checks work there, SPEC.md §10.2), so it is covered.
list_covered() {
    for f in .claude/skills/*/SKILL.md \
             .claude/agents/*.md \
             .claude/hooks/*.sh \
             .claude/settings.template.json \
             scripts/kit-config.sh; do
        if [ -f "$f" ]; then
            printf '%s\n' "$f"
        fi
    done | LC_ALL=C sort
}

files=$(list_covered)
if [ -z "$files" ]; then
    echo "gen-manifest: no kit-managed files found under $KIT_ROOT — wrong root?" >&2
    exit 1
fi

printf '%s\n' "$files" | while IFS= read -r f; do
    $HASH "$f"
done > "$TMP"

case "${1:-}" in
    "")
        cat "$TMP" > "$MANIFEST"
        n=$(grep -c . "$MANIFEST")
        echo "gen-manifest: wrote $MANIFEST ($n files)"
        ;;
    --check)
        if [ ! -f "$MANIFEST" ]; then
            echo "gen-manifest: $MANIFEST is missing — manifest drifted — run scripts/gen-manifest.sh" >&2
            exit 1
        fi
        if ! diff -u "$MANIFEST" "$TMP" >&2; then
            echo "gen-manifest: manifest drifted — run scripts/gen-manifest.sh" >&2
            exit 1
        fi
        echo "gen-manifest: manifest is current"
        ;;
    *)
        echo "gen-manifest: unknown argument '$1' (usage: gen-manifest.sh [--check])" >&2
        exit 2
        ;;
esac
