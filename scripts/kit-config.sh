#!/usr/bin/env bash
# kit-config.sh — Tier-0 reader for the project profile (.claude/kit.yaml).
#
# SPEC citation: SPEC.md §10.2 (v2.0 ships `scripts/kit-config.sh get
# <dotted.key>`, ~40-line bash reader) honoring ONLY the §10.3 parse
# contract: two-space indent per level, one `key: value` per line, no flow
# style, no anchors, single-line double-quoted strings. This is NOT a YAML
# parser. Tier-0 per §10: bash + coreutils only; bash-3.2-safe.
#
# Usage: kit-config.sh get <dotted.key> [default]
#   Prints the value (surrounding double quotes stripped, trailing
#   " # comment" dropped — but a '#' inside quotes is kept) and exits 0.
#   Absent/empty key: prints the default and exits 0 when one is given;
#   otherwise prints nothing and exits 1.
# Env: KIT_CONFIG_FILE overrides the config path (default: .claude/kit.yaml).
#
# Hooks stay standalone (SPEC.md §4.5) — instead of calling this script they
# use the documented one-line pattern (indent = two spaces per level; shown
# here for gates.modes.<key> at depth 2):
#   sed -n 's/^    <key>:[[:space:]]*//p' .claude/kit.yaml | sed 's/[[:space:]]*#.*$//;s/^"\(.*\)"$/\1/' | head -n 1

set -euo pipefail

[ "${1:-}" = "get" ] && [ -n "${2:-}" ] || {
    echo "usage: kit-config.sh get <dotted.key> [default]" >&2; exit 2; }

FILE="${KIT_CONFIG_FILE:-.claude/kit.yaml}"
val=""
if [ -f "$FILE" ]; then
    val=$(awk -v path="$2" '
        BEGIN { n = split(path, want, "."); depth = 0 }
        /^[[:space:]]*(#|$)/ { next }                 # blank / comment-only lines
        {
            match($0, /^ */); ind = int(RLENGTH / 2)  # §10.3: two-space indent
            if (ind < depth) exit                     # left the matched block
            if (ind > depth) next                     # child of a non-matching sibling
            line = substr($0, RLENGTH + 1)
            i = index(line, ":"); if (i == 0) next
            if (substr(line, 1, i - 1) != want[depth + 1]) next
            depth++
            if (depth < n) next                       # matched a parent; descend
            v = substr(line, i + 1); sub(/^[[:space:]]+/, "", v)
            if (v ~ /^"/) { sub(/^"/, "", v); sub(/".*$/, "", v) }  # quoted: keep interior "#"
            else { sub(/[[:space:]]#.*$/, "", v); sub(/[[:space:]]+$/, "", v) }
            print v; exit
        }' "$FILE")
fi
if [ -n "$val" ]; then printf '%s\n' "$val"; exit 0; fi
if [ "$#" -ge 3 ]; then printf '%s\n' "$3"; exit 0; fi
exit 1
