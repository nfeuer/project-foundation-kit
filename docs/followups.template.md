# Follow-ups

Durable log of deferred decisions, accepted spec drift, and cross-cutting work
that shouldn't live in a code comment. Managed by the `followup-tracking` skill.
Add an entry when you finish a unit of work and notice something deferred.
Resolved entries move to `followups-archive.md`.

> A bug belongs in the tracker, not here. Work you'll finish in the current PR
> belongs in the PR, not here. This file is for things intentionally left for
> later.

---

<!-- Example entries — replace with real ones. -->

### S01 — <short title>

- **Spec:** `spec.md §<N.M>`
- **Status:** open (deferred)
- **Gap:** <2–5 sentences: what the code does now, what it should do, what action
  is needed. If trigger-gated, name the condition that should prompt the work.>

### AUTH-02 — <short title>

- **Spec:** `docs/decisions/2026-01-auth.md#tokens`
- **Status:** spec-update-pending
- **Gap:** Behavior diverged from the spec (token TTL is now config-driven, spec
  still says hardcoded). Update §X in a follow-up PR; noted here so it isn't lost.

---

## How to add an entry

```markdown
### <ID> — <short title>

- **Spec:** `<path/to/spec.md> §<N.M>`
- **Status:** open | open (deferred) | open (trigger-gated) | spec-update-pending
- **Gap:** <what's missing and what to do>
```

- **ID prefix** groups related items (`S<NN>` = slice, `AUTH` = subsystem, etc.).
  Keep IDs stable once assigned — they're referenced from PRs and design docs.
- On resolution: mark `✅ RESOLVED <YYYY-MM-DD>` inline, then move the entry to
  `followups-archive.md` so this file stays short.
