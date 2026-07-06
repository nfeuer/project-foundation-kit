# secret-scan-diff.sh false-positives when the local trunk ref is stale

- **Date:** 2026-07-06
- **Area:** `.claude/hooks/secret-scan-diff.sh` / git branch-diff scope
- **Symptom:** `BLOCKED: Possible secret(s) detected in diff.` naming a line
  you did not touch on this branch — e.g.
  `[AWS access key ID] .github/workflows/kit-ci.yml: printf 'AWS_KEY = "%s"\n' "AKIAABCDEFGHIJKLMNOP"` —
  and appending the `# pragma: allowlist secret` opt-out appears to have no
  effect (the reported line still shows without the pragma).

## Root cause

With nothing staged, the hook scans `git diff <trunk>...HEAD -U0`, where
`<trunk>` is the **local** ref named by `trunk_branch` in `.claude/kit.yaml`.
In a fresh clone checked out on a feature branch (CI runners, remote agent
sessions), local `main` can point far behind `origin/main`, so the scanned
range includes every already-merged upstream commit — and any key-shaped
string one of them added (here: the planted test vector in kit-ci.yml's
behavioral hook test) is reported as if the branch added it. The pragma edit
"not working" is the same confusion: the hook scans *committed* added lines,
so a working-tree edit — and the pragma-less historical copy of the line —
is what it keeps seeing.

## Solution

Sync the local trunk ref, then re-run:

```bash
git fetch origin main && git branch -f main origin/main
bash .claude/hooks/secret-scan-diff.sh </dev/null   # rc 0 = clean
```

Independently, known intentional matches should carry the opt-out on the
committed line itself — kit-ci.yml's planted test key now ends with
`# pragma: allowlist secret (test vector)` so historical-range scans stay
quiet.

## How to recognize it next time

The scanner names a file/line your branch never modified, or `git diff
main...HEAD --stat` is suspiciously large (dozens of files for a small
branch). Check `git log main..origin/main --oneline | head` — any output
means the local trunk is stale and the scan range is wrong.
