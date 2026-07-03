## Summary

<!--
One paragraph or short bullet list: what changed and why. Not how — the diff
shows how. Focus on intent and motivation.
-->


## Spec citation

<!--
Every design change must cite the spec section it implements or diverges from.
If this PR makes no architectural or behavioral change, write "no design change."
-->

- [ ] Implements `spec_v3.md §<N.M>` — _<brief note>_
- [ ] No design change

## What was tested

<!--
Evidence, not assertions. Link to CI run, paste test output, describe manual
steps. "I tested it locally" is not evidence. "pytest output shows 42 passed,
0 failed — see CI run #N" is.
-->

- [ ] Unit tests: `pytest tests/unit/` — <N passed, 0 failed>
- [ ] Integration tests: `pytest tests/integration/` — <N passed / N/A>
- [ ] Manual verification: <steps taken or N/A>
- [ ] Coverage ratchet: <current % vs baseline % / N/A>

## Risk and rollback

<!--
How bad is the worst-case failure? How do you reverse it?
-->

**Risk:** <low | medium | high> — <one sentence on the failure mode>

**Rollback:** <revert the PR / feature flag off / migration rollback command>

## Docs

- [ ] Narrative docs updated in the same PR (or no docs affected)
- [ ] Changelog entry added
- [ ] ADR written: `docs/decisions/<NNNN-slug>.md` (or no ADR needed)

## Follow-ups

- [ ] New follow-ups added to `docs/followups.md`: <IDs or "none">
- [ ] Existing follow-ups closed: <IDs or "none">

---

<!-- Pre-PR gate must be clean before opening. Run the pre-pr skill. -->
