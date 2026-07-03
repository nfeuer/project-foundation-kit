#!/bin/bash
# branch-conflict-check/check.sh — detect file-set overlap between this branch
# and every other open PR, so merges get sequenced deliberately instead of
# colliding at review time.
#
# Prints one block per conflicting PR:
#   PR #<n>  <headRefName>
#     path/to/shared/file.py
#     another/shared/file.py
#
# Exits 0 whether or not overlaps are found; the caller (human or agent)
# decides what to do. No-ops cleanly (exit 0) if gh is missing or not
# authenticated — does not fail the pre-PR gate.
#
# Usage:  bash check.sh [base-branch]
#   base-branch defaults to "main"; override with "master", "develop", etc.
#
# Companion to the branch-conflict-check skill. Run it standalone or call it
# from the pre-pr gate as an advisory step.

set -uo pipefail

BASE="${1:-main}"

# Scratch directory — cleaned up on exit regardless of how the script exits.
SCRATCH=$(mktemp -d)
trap 'rm -rf "$SCRATCH"' EXIT

# --- Require gh; degrade gracefully if absent or not authed ---
if ! command -v gh &>/dev/null; then
    echo "[branch-conflict-check] gh not found — skipping overlap check." >&2
    exit 0
fi
if ! gh auth status &>/dev/null 2>&1; then
    echo "[branch-conflict-check] gh not authenticated — skipping overlap check." >&2
    exit 0
fi

# --- Resolve the current branch ---
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
if [[ -z "$CURRENT_BRANCH" ]]; then
    echo "[branch-conflict-check] Not on a named branch (detached HEAD?) — exiting." >&2
    exit 0
fi

# --- Collect this branch's changed files vs the base, sorted for comm ---
MY_FILES="$SCRATCH/my_files.txt"
git diff "${BASE}...HEAD" --name-only 2>/dev/null | sort > "$MY_FILES"

if [[ ! -s "$MY_FILES" ]]; then
    echo "No changed files on ${CURRENT_BRANCH} vs ${BASE}."
    exit 0
fi

FILE_COUNT=$(wc -l < "$MY_FILES")
echo "Checking ${CURRENT_BRANCH} vs ${BASE} (${FILE_COUNT} changed file(s)) ..."
echo ""

FOUND_OVERLAP=0

# --- List all open PRs: one line per PR as "<number> <headRefName>" ---
PR_LIST="$SCRATCH/pr_list.txt"
gh pr list --state open --json number,headRefName \
    --jq '.[] | "\(.number) \(.headRefName)"' 2>/dev/null > "$PR_LIST" || true

# --- For each PR, compute the file-set intersection ---
while IFS=' ' read -r pr_num pr_ref; do
    # Skip the PR that belongs to the branch we're checking
    [[ "$pr_ref" == "$CURRENT_BRANCH" ]] && continue

    # Fetch sorted file paths for this PR
    PR_FILES="$SCRATCH/pr_${pr_num}.txt"
    gh pr view "$pr_num" --json files \
        --jq '.files[].path' 2>/dev/null | sort > "$PR_FILES" || continue

    # Nothing to intersect if the PR has no files
    [[ -s "$PR_FILES" ]] || continue

    # comm -12: lines present in both sorted lists = the intersection
    OVERLAP="$SCRATCH/overlap_${pr_num}.txt"
    comm -12 "$MY_FILES" "$PR_FILES" > "$OVERLAP"

    if [[ -s "$OVERLAP" ]]; then
        FOUND_OVERLAP=1
        echo "PR #${pr_num}  (${pr_ref})"
        while IFS= read -r shared_file; do
            echo "  ${shared_file}"
        done < "$OVERLAP"
        echo ""
    fi
done < "$PR_LIST"

if [[ $FOUND_OVERLAP -eq 0 ]]; then
    echo "No file overlap found between ${CURRENT_BRANCH} and other open PRs."
fi

exit 0
