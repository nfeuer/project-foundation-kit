---
name: release
description: Turn merged PRs and conventional commits since the last tag into a versioned changelog entry and a tagged release — semver bump derived automatically from commit types
---

# Release

Run this when you are ready to cut a release from `trunk_branch`. It collects
every commit since the last tag, derives the semver bump from conventional-commit
types, groups entries into a changelog section, and — after a dry-run review —
tags and optionally drafts a GitHub release.

**Profile-driven.** Steps tagged `# kit.yaml → <key>` read that value from
`.claude/kit.yaml`; defaults shown are for a conventional repository. The keys
`release.changelog_file`, `release.auto_tag`, and `release.require_spec_citations`
must be present (they are added by the coordinator when this skill is wired in);
`trunk_branch` is the shared root key.

**Default: dry-run.** Steps 1–6 are always safe to run — they read only. No file
is written and no tag is created until you confirm at Step 7. Stop at Step 6,
review the output block, and proceed only when the computed version and changelog
diff look correct.

## Guardrails

- **Never tag on a dirty tree.** If `git status --porcelain` is non-empty, abort.
- **Never overwrite an existing tag.** If the computed tag already exists locally or
  on the remote, abort with a clear message — do not force-push or delete.
- **Never run on a non-trunk branch.** Confirm `HEAD` is on `trunk_branch` before
  doing anything that writes.

---

## Steps

### 1. Guard — working tree and branch

```bash
# kit.yaml → trunk_branch
git status --porcelain          # must be empty; abort if not
git branch --show-current       # must equal trunk_branch value; abort if not
```

If either check fails, stop immediately. Print the exact failure (dirty files
listed, or current branch vs. expected) and do not proceed.

### 2. Find the last release tag and collect commits since

```bash
git describe --tags --abbrev=0 2>/dev/null || echo "NO_PRIOR_TAG"
```

If the output is `NO_PRIOR_TAG`, collect all commits in the repository:

```bash
git log --format="%H %s" --reverse
```

Otherwise collect only commits after the last tag:

```bash
git log <last_tag>..HEAD --format="%H %s" --reverse
```

Record: last tag (or `(none)`), commit count, raw commit list.

### 3. Parse conventional commits and derive the semver bump

For each commit subject, match against `type(scope)!: subject` or
`type(scope): subject` using the allowed types from `docs/COMMIT_CONVENTION.md`:
`feat`, `fix`, `docs`, `refactor`, `test`, `perf`, `chore`, `revert`.

Bump rules (highest wins across all commits):

| Signal | Bump |
|---|---|
| `feat!:` / `BREAKING CHANGE:` in commit body footer | **major** |
| `feat:` or `feat(scope):` | **minor** |
| `fix:` or `fix(scope):` | **patch** |
| anything else parseable | no version bump on its own |

If no commit warrants a version bump (only `docs`, `chore`, `refactor`, `test`,
`perf`, `revert`), warn the human: *"No feat or fix commits found — this release
would be a no-op version bump. Confirm you still want to proceed."* Do not abort;
let them decide.

### 4. Compute the next semver and check for tag collision

Parse the last tag as `vMAJOR.MINOR.PATCH` (strip a leading `v` if present).
Apply the bump to get `next_version`. Re-attach the `v` prefix:

```bash
git tag --list "v${next_version}"   # must return nothing; abort if tag exists
git ls-remote --tags origin "refs/tags/v${next_version}"  # same check on remote
```

Record: `last_tag → next_tag`, bump reason.

### 5. Fetch PR numbers and spec citations for each commit

For each commit hash collected in Step 2, pull its full message to extract:

- **PR number**: look for `(#NNN)` in the subject or `Fixes: #NNN` / `Closes: #NNN`
  in the body.
- **Spec citation**: look for `Ref:` lines containing `§` (the section marker from
  `capabilities.spec.section_marker` in kit.yaml, default `§`).

```bash
git log -1 --format="%B" <commit_hash>
```

### 6. Group entries and emit warnings

Group the parsed commits into four sections (omit a section entirely if empty):

- **Breaking Changes** — any commit with `!` type or `BREAKING CHANGE:` footer
- **Features** — `feat` commits
- **Fixes** — `fix` commits
- **Other** — all remaining parseable commits (`docs`, `chore`, `refactor`, etc.)

For each entry, format:
```
- <short subject> (<PR #NNN if found>)  [§X.Y if found]
```

**Warn on unparseable commits.** Any commit whose subject does not match
`type(scope)?: subject` is unparseable. Do not silently drop it. Collect all such
commits into a WARNINGS block and list them (hash + raw subject) for the human to
triage. They may belong in Other or indicate a convention violation.

**Spec citation check.**
**Applies when** `release.require_spec_citations` is true in `.claude/kit.yaml`.
If false, skip and mark N/A.

For every `feat` or `fix` commit that has no `§` citation, emit a warning:
*"Release-worthy commit with no spec citation: `<hash> <subject>`."* The release
is not blocked, but the warnings must be visible in the output.

---

**Stop here for dry-run review.** Print the full Output block (see below). Do not
write any file or create any tag until the human confirms the version and changelog
diff are correct.

---

### 7. Write the changelog entry

```bash
# kit.yaml → release.changelog_file  (default: docs/changelog.md)
```

Prepend a new section to the changelog file using this format:

```markdown
## [v<next_version>] — YYYY-MM-DD

### Breaking Changes
- ...

### Features
- ...

### Fixes
- ...

### Other
- ...
```

Use today's date (ISO 8601). Omit sections that are empty. After writing, show
the diff:

```bash
git diff -- <changelog_file>
```

### 8. Tag the release

**Applies when** `release.auto_tag` is true in `.claude/kit.yaml`. If false, stop
here: report the computed version, show the changelog diff, and instruct the human
to run `git tag v<next_version> && git push origin v<next_version>` manually.

```bash
git tag -a "v${next_version}" -m "Release v${next_version}"
git push origin "v${next_version}"
```

Confirm the push succeeded before proceeding to Step 9.

### 9. Draft a GitHub release

**Applies when** `release.auto_tag` is true (tag was just created in Step 8).

```bash
gh release create "v${next_version}" \
  --draft \
  --title "v${next_version}" \
  --notes-file <(echo "<changelog section text>")
```

The release is always created as `--draft`. A human promotes it to published.
Print the URL returned by `gh release create`.

---

## Output

Fill this in with real results after every run. In dry-run mode, all write-path
lines show `(dry-run — not applied)`.

```
## Release

Last tag:        v<X.Y.Z>  (or "(none)")
Next version:    v<X.Y.Z>
Bump reason:     <major — BREAKING CHANGE in <hash> | minor — feat in <hash> | patch — fix in <hash> | none — no feat/fix commits>

### Changelog preview

## [v<X.Y.Z>] — YYYY-MM-DD

#### Breaking Changes
- <subject> (#NNN) [§X.Y]

#### Features
- <subject> (#NNN) [§X.Y]

#### Fixes
- <subject> (#NNN)

#### Other
- <subject>

### Warnings
- Unparseable commits (not in conventional-commit format):
  - <hash> <raw subject>
  - ...
- Spec citations missing on release-worthy commits (release.require_spec_citations=true):
  - <hash> <subject>
  - ...
- <none>

### Actions
- [ ] Changelog written to <release.changelog_file>:  <done / dry-run — not applied>
- [ ] Tag created and pushed:                          <v<X.Y.Z> / dry-run — not applied / N/A — auto_tag=false>
- [ ] GitHub draft release:                            <<URL> / dry-run — not applied / N/A — auto_tag=false>

Blocked: <YES — <reason> | NO>
```
