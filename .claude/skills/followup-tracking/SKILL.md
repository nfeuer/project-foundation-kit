---
name: followup-tracking
description: Capture deferred decisions, accepted drift, and cross-cutting TODOs in a durable follow-ups log instead of letting them rot in code comments — with a stable-ID entry format and a close/archive lifecycle
---

# Follow-up Tracking

**Profile-driven.** The followups file lives at `<docs.dir>/followups.md`, where `docs.dir` is `capabilities.docs.dir` from `.claude/kit.yaml` (default: `docs`).

A TODO in a code comment is invisible the moment the PR merges. This skill keeps
deferred work in one durable, greppable place — `docs/followups.md` — so it gets
addressed on purpose later instead of being rediscovered by accident. Run it when
finishing any unit of work.

## What belongs here
- **Deferred decisions** — "we chose X for now; revisit when Y lands."
- **Accepted drift** — code intentionally diverges from the spec, spec update
  deferred (`spec-update-pending`).
- **Trigger-gated work** — don't build it speculatively; note the condition that
  should trigger it.
- **Cross-cutting cleanups** — too big for this PR, shouldn't be forgotten.

What does *not* belong: a bug (file it / fix it), or work you'll do in this same
PR (just do it).

## Entry format
Append to `<docs.dir>/followups.md` (`capabilities.docs.dir` from `kit.yaml`, default: `docs`). Every entry has a stable ID so design docs and
commit messages can reference it:

```markdown
### <ID> — <short title>

- **Spec:** `<path/to/spec.md> §<N.M>`   (or the design doc + anchor)
- **Status:** open | open (deferred) | open (trigger-gated) | spec-update-pending
- **Gap:** <2–5 sentences: what the code does now, what it should do, what action
  is needed, and — if trigger-gated — the condition that should prompt it.>
```

Choose an ID prefix that groups related items (e.g. `S12` = slice 12, `AUTH` =
auth subsystem, `TI-FU3` = time-intent follow-up). Keep IDs stable once assigned.

### Example
```markdown
### S07 — recurring-intent routing is a stub

- **Spec:** `spec_v3.md §25`
- **Status:** open (deferred to Plan 2/3)
- **Gap:** The router returns AUTOMATION for kind="recurring", but the scheduler
  only logs and skips — nothing creates the recurrence yet. Wire the handoff when
  the constraint slice lands.
```

## Lifecycle
- **Add** at the end of a slice/PR: scan your diff, append entries. The `pre-pr`
  and `doc-sync` skills both prompt for this.
- **Reference** by ID from PRs and design docs so the thread is traceable.
- **Close** when the work lands: mark `✅ RESOLVED <date>` inline, then move the
  entry to `docs/followups-archive.md` so the active file stays short.

## Output
```
## Follow-ups
- Added: <IDs + titles / none>
- Closed: <IDs / none>
- Active count: <n>
```
