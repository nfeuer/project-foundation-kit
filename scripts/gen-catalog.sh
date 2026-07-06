#!/usr/bin/env bash
# gen-catalog.sh — regenerate the README workflow catalog and print the
# strictness default maps from SKILL.md frontmatter.
#
# SPEC citation: SPEC.md §3 (generation contract — one source of truth,
# mechanically enforced), §4.2 (the gate key set), §4.3 (strictness →
# default maps). Tier-0 per SPEC.md §10: bash + git + coreutils only; must
# run on macOS bash 3.2 and Linux.
#
# Usage:
#   scripts/gen-catalog.sh           validate + rewrite the README catalog in
#                                    place between <!-- catalog:begin/end -->
#   scripts/gen-catalog.sh --check   validate + exit 1 if the README catalog
#                                    drifted from the frontmatter
#   scripts/gen-catalog.sh --modes   print the §4.3 strictness default-map table
#
# Env: KIT_ROOT overrides the repo root (default: git rev-parse --show-toplevel).

set -euo pipefail

KIT_ROOT="${KIT_ROOT:-$(git rev-parse --show-toplevel)}"
cd "$KIT_ROOT"

README="README.md"
BEGIN_MARK='<!-- catalog:begin -->'
END_MARK='<!-- catalog:end -->'

# The §4.2 key set, pre-sorted LC_ALL=C. Gates with no key do not exist.
GATE_KEYS="branch_conflict build_artifact capture coverage_ratchet \
credential_files docs_sync flaky_triage integration_tests lint_types_tests \
migration_check observability_check perf_budget prompt_regression \
secrets_scan security_review spec_drift sync_health test_gap ui_build \
worktree_isolation"

# Trend gates demoted to suggest at prototype strictness (§4.3).
TREND_GATES="coverage_ratchet perf_budget prompt_regression"
# Deterministic-protective gates pinned enforce at every level (§2.2, §4.3).
PINNED_GATES="secrets_scan credential_files migration_check"

DATA=$(mktemp "${TMPDIR:-/tmp}/gen-catalog.data.XXXXXX")
SCRATCH=$(mktemp "${TMPDIR:-/tmp}/gen-catalog.scratch.XXXXXX")
trap 'rm -f "$DATA" "$SCRATCH"' EXIT

# ---------------------------------------------------------------------------
# Frontmatter parsing (§3 generation contract: single-line scalars, values are
# bare tokens or double-quoted strings, optionally followed by a # comment).
# ---------------------------------------------------------------------------

# Print the frontmatter body of $1 (between the first two '---' lines).
frontmatter_of() {
    head -n 1 "$1" | grep -q '^---[[:space:]]*$' || return 0
    sed -n '2,$p' "$1" | sed -n '1,/^---[[:space:]]*$/p' | sed '$d'
}

# field_from <frontmatter-text> <key> — print the cleaned scalar value.
field_from() {
    line=$(printf '%s\n' "$1" | grep "^$2:" | head -n 1) || true
    if [ -z "$line" ]; then
        printf ''
        return 0
    fi
    val=${line#*:}
    val=$(printf '%s' "$val" | sed 's/^[[:space:]]*//')
    case "$val" in
        \"*)
            # Double-quoted string; anything after the closing quote is dropped.
            val=$(printf '%s' "$val" | sed 's/^"\(.*\)".*$/\1/')
            ;;
        *)
            # Bare token; strip trailing comment and whitespace.
            val=${val%%#*}
            val=$(printf '%s' "$val" | sed 's/[[:space:]]*$//')
            ;;
    esac
    printf '%s' "$val"
}

key_in_set() { # key_in_set <key> <space-separated set>
    for k in $2; do
        [ "$1" = "$k" ] && return 0
    done
    return 1
}

# ---------------------------------------------------------------------------
# Collect + validate (validation runs in every mode).
# Data file: name<TAB>description<TAB>cost<TAB>protects<TAB>requires<TAB>gate_key<TAB>ci_job
# ---------------------------------------------------------------------------

violations=0
violation() {
    echo "gen-catalog: $1" >&2
    violations=1
}

found_any=0
for f in .claude/skills/*/SKILL.md; do
    [ -f "$f" ] || continue
    found_any=1
    fm=$(frontmatter_of "$f")
    name=$(field_from "$fm" name)
    description=$(field_from "$fm" description)
    cost=$(field_from "$fm" cost)
    protects=$(field_from "$fm" protects)
    requires=$(field_from "$fm" requires)
    gate_key=$(field_from "$fm" gate_key)
    ci_job=$(field_from "$fm" ci_job)

    for pair in "name=$name" "description=$description" "cost=$cost" \
                "protects=$protects" "requires=$requires" \
                "gate_key=$gate_key" "ci_job=$ci_job"; do
        fname=${pair%%=*}
        fval=${pair#*=}
        if [ -z "$fval" ]; then
            violation "$f: missing or empty frontmatter field '$fname' (SPEC.md §3)"
        fi
    done

    if [ -n "$cost" ]; then
        case "$cost" in
            free|cheap|subagents) : ;;
            *) violation "$f: cost '$cost' is not one of free|cheap|subagents (SPEC.md §3)" ;;
        esac
    fi
    if [ -n "$gate_key" ] && [ "$gate_key" != "none" ]; then
        if ! key_in_set "$gate_key" "$GATE_KEYS"; then
            violation "$f: gate_key '$gate_key' is not in the SPEC.md §4.2 key set (or 'none')"
        fi
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$name" "$description" "$cost" "$protects" "$requires" "$gate_key" "$ci_job" >> "$DATA"
done

if [ "$found_any" -eq 0 ]; then
    echo "gen-catalog: no .claude/skills/*/SKILL.md found under $KIT_ROOT" >&2
    exit 1
fi

# A gate_key other than 'none' and 'capture' must be claimed by exactly one
# skill ('capture' is explicitly shared, SPEC.md §6.3).
dups=$(cut -f6 "$DATA" | grep -v '^none$' | grep -v '^capture$' | grep -v '^$' \
        | LC_ALL=C sort | uniq -d) || true
if [ -n "$dups" ]; then
    for d in $dups; do
        claimants=$(LC_ALL=C sort "$DATA" | cut -f1,6 | grep "	$d\$" | cut -f1 | tr '\n' ' ')
        violation "gate_key '$d' is claimed by more than one skill: $claimants(only 'capture' may be shared, SPEC.md §6.3)"
    done
fi

if [ "$violations" -ne 0 ]; then
    echo "gen-catalog: validation failed — fix the frontmatter above (SPEC.md §3)" >&2
    exit 1
fi

LC_ALL=C sort -o "$DATA" "$DATA"

# ---------------------------------------------------------------------------
# Catalog rendering (the marker interior).
# ---------------------------------------------------------------------------

render_interior() {
    echo "_Generated from skill frontmatter by \`scripts/gen-catalog.sh\` — edit the skills' frontmatter, not this table (kit-ci fails on drift)._"
    echo ""
    echo '### Gates (mode-mapped via `gates.modes.<gate key>`)'
    echo ""
    echo "| Skill | Protects | Cost | Requires | Gate key | CI job |"
    echo "|---|---|---|---|---|---|"
    while IFS='	' read -r name description cost protects requires gate_key ci_job; do
        [ "$gate_key" = "none" ] && continue
        [ "$requires" = "nothing" ] && requires='—'
        [ "$ci_job" = "none" ] && ci_job='—'
        printf '| %s | %s | %s | %s | `%s` | %s |\n' \
            "$name" "$protects" "$cost" "$requires" "$gate_key" "$ci_job"
    done < "$DATA"
    echo ""
    echo "### Workflows & conventions (never mode-gated)"
    echo ""
    echo "| Skill | Protects | Cost | Requires |"
    echo "|---|---|---|---|"
    while IFS='	' read -r name description cost protects requires gate_key ci_job; do
        [ "$gate_key" = "none" ] || continue
        [ "$requires" = "nothing" ] && requires='—'
        printf '| %s | %s | %s | %s |\n' "$name" "$protects" "$cost" "$requires"
    done < "$DATA"
}

render_readme() { # print the full regenerated README to stdout
    if ! grep -q "^$BEGIN_MARK\$" "$README" || ! grep -q "^$END_MARK\$" "$README"; then
        echo "gen-catalog: $README is missing the '$BEGIN_MARK' / '$END_MARK' markers — cannot place the catalog (SPEC.md §3)" >&2
        exit 1
    fi
    sed -n "1,/^$BEGIN_MARK\$/p" "$README"
    render_interior
    sed -n "/^$END_MARK\$/,\$p" "$README"
}

# ---------------------------------------------------------------------------
# --modes: the §4.3 strictness default-map table, derived mechanically.
# ---------------------------------------------------------------------------

# Static cost class for keys not owned by any skill (they belong to hooks /
# agents / pre-pr steps).
static_cost() {
    case "$1" in
        secrets_scan|credential_files|worktree_isolation) echo "free" ;;
        security_review|test_gap|spec_drift) echo "subagents" ;;
        integration_tests|ui_build|build_artifact) echo "cheap" ;;
        *) echo "cheap" ;;
    esac
}

render_modes() {
    echo "| Gate key | prototype | standard | production |"
    echo "|---|---|---|---|"
    for key in $GATE_KEYS; do
        # Worst-case cost across owning skills; static table when unowned.
        owned_costs=$(cut -f3,6 "$DATA" | grep "	$key\$" | cut -f1) || true
        owned_ci=$(cut -f6,7 "$DATA" | grep "^$key	" | cut -f2 | grep -v '^none$') || true
        if [ -n "$owned_costs" ]; then
            if printf '%s\n' "$owned_costs" | grep -q '^subagents$'; then
                cost="subagents"
            else
                cost="cheap"
            fi
        else
            cost=$(static_cost "$key")
        fi

        production="enforce"
        if [ "$cost" = "subagents" ]; then standard="suggest"; else standard="enforce"; fi
        prototype="$standard"
        if key_in_set "$key" "$TREND_GATES"; then prototype="suggest"; fi

        # Pinned overrides win at every level (§4.3 invariants):
        # deterministic-protective gates, and CI-backed gates (§2.3).
        if key_in_set "$key" "$PINNED_GATES" || [ -n "$owned_ci" ]; then
            prototype="enforce"; standard="enforce"; production="enforce"
        fi

        printf '| %s | %s | %s | %s |\n' "$key" "$prototype" "$standard" "$production"
    done
    echo ""
    echo "_Preset overlays (SPEC.md §4.3): \`llm-app\` pins \`prompt_regression\` to enforce; \`library\`/solo presets default \`worktree_isolation\` to suggest._"
    echo "_generated by scripts/gen-catalog.sh --modes — the normative copy lives in docs/PROFILE.md once §4 ships_"
}

# ---------------------------------------------------------------------------
# Mode dispatch.
# ---------------------------------------------------------------------------

case "${1:-}" in
    "")
        render_readme > "$SCRATCH"
        cat "$SCRATCH" > "$README"
        echo "gen-catalog: wrote catalog into $README"
        ;;
    --check)
        render_readme > "$SCRATCH"
        if ! diff -u "$README" "$SCRATCH" >&2; then
            echo "gen-catalog: catalog drifted — run scripts/gen-catalog.sh" >&2
            exit 1
        fi
        echo "gen-catalog: catalog is current"
        ;;
    --modes)
        render_modes
        ;;
    *)
        echo "gen-catalog: unknown argument '$1' (usage: gen-catalog.sh [--check|--modes])" >&2
        exit 2
        ;;
esac
