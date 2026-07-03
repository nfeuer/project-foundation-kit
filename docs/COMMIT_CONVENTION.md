# Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/).
Every commit message must parse as `type(scope): subject`. This drives automated
changelog generation, semantic versioning, and makes `git log` useful.

## Format

```
type(scope): short imperative subject (≤72 chars)

Optional body — explain *why*, not *what*. The diff shows what.

Footer:
Co-Authored-By: Name <email>
Fixes: #N   (closes the issue on merge)
Ref: ADR-0003, spec_v3.md §12
```

## Allowed types

| Type | When to use |
|---|---|
| `feat` | New capability visible to users or callers |
| `fix` | Bug fix |
| `docs` | Documentation only — no code change |
| `refactor` | Restructure without changing behavior |
| `test` | Add or fix tests only |
| `perf` | Performance improvement |
| `chore` | Tooling, deps, config, CI — nothing a user notices |
| `revert` | Undoes a previous commit (include original subject in body) |

Use `!` for breaking changes: `feat(api)!: rename complete() parameter`.

## Scope

Optional but encouraged. Use the subsystem or module name: `scheduler`,
`discord`, `tasks`, `llm`, `auth`, `db`, `ci`, `docker`.

## Why this matters

- `feat` and `fix` commits auto-populate the changelog.
- Breaking-change markers (`!` or `BREAKING CHANGE:` footer) trigger a major
  version bump in semver tooling.
- Scopes let you filter `git log --grep='^feat(scheduler)'` for release notes.
- Consistent history makes `git bisect` faster and blame more readable.

## Footer discipline

Always include attribution and traceability footers on substantive commits:

```
Co-Authored-By: Claude <noreply@anthropic.com>
Ref: spec_v3.md §14, docs/decisions/0002-use-sqlite-wal.md
Fixes: #42
```

`Fixes:` closes the linked issue on merge. `Ref:` links design context without
closing. Use both when applicable.

## Examples

```
feat(scheduler): add dynamic rescheduling on missed deadlines

Closes the gap identified in the nightly-audit report — tasks that were
due more than 2h ago now get a new slot instead of staying overdue forever.

Ref: spec_v3.md §18.3, docs/followups.md #S09
Co-Authored-By: Claude <noreply@anthropic.com>
```

```
fix(discord): handle rate-limit 429 with exponential backoff

Previously the bot crashed on burst sends. Now retries up to 3 times
with jitter. Silent failures were the bug (no fallback_activated event).

Fixes: #37
```

```
chore(ci): pin uv to 0.4.x to unblock mypy

Version drift in 0.5 changed how extras resolve; pinning until upstream fix.
```

```
docs(adr): add 0003-model-abstraction-layer

Ref: spec_v3.md §6
```
