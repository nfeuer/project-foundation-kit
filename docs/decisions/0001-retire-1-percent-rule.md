# 0001. Retire the 1% rule in favor of the trigger-index contract

**Status:** proposed
**Date:** 2026-07-31
**Author:** Claude 5 skill refresh (docs/plans/claude5-skill-refresh.md)

---

## Context

`using-the-kit` dispatches skills via the "1% rule": *"If you think there is even
a 1% chance a kit skill applies … you MUST invoke it."* That wording was written
to overcome older models' reluctance to check. The Claude 5 generation follows
instructions literally, so a doubt-threshold fused to compliance emphasis reads
as "invoke a skill on nearly every turn" — the overtriggering cost problem
`SPEC.md` §1 names, and §7 ("Chaining replaces the 1% rule") already designates
for replacement. The skill prose never caught up to the spec.

---

## Decision

We will remove all doubt-threshold dispatch language and dispatch purely on the
trigger-index contract: scan the index before acting; if a row's condition
matches, invoke that skill. The anti-skip duty ("Reporting N/A is fine. Skipping
the check silently is not.") is retained — the threshold goes, not the duty.

---

## Options Considered

### Option A: Trigger-index contract ✅ chosen

**Pros:** matches SPEC §7; condition-matching is what literal-following models
execute well; removes the overtrigger cue at its source.
**Cons:** requires a companion sweep (`writing-kit-skills`, `CLAUDE.template.md`,
`README.md`) and a changelog note for adopted projects' `CLAUDE.md`.

### Option B: Keep the 1% rule ❌ rejected

**Pros:** no edits; familiar to existing adopters.
**Cons:** contradicts the spec's own §7; on Claude 5 it produces near-universal
skill invocation — the token/latency cost the rule was never meant to buy.

---

## Consequences

Dispatch quality now depends entirely on trigger-index row quality — a skill
without a sharp index row will not fire ("no row, no trigger" becomes the
registration rule). Adopted projects must hand-update the 1%-rule paragraph
bootstrap copied into their `CLAUDE.md`.

---

## Related

- SPEC.md §1, §7 (the authority this catches up to)
- docs/plans/claude5-skill-refresh.md — Wave 1, pattern PR-1
