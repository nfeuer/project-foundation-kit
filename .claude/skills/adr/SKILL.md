---
name: adr
description: Create an Architecture Decision Record when a non-obvious design choice is made — captures context, options, rationale, and tradeoffs in a durable doc
cost: free
protects: "The reasoning behind a hard design choice gets written down, including the alternatives you rejected, so no one has to guess or re-argue it later."
requires: nothing
gate_key: none
ci_job: none
---

# ADR

An Architecture Decision Record (ADR) is a short document that answers the
question a future engineer will inevitably ask: *"Why did we do it this way?"*
Write one whenever you make a choice that isn't obvious from the code alone —
not for every line, but for every fork in the road where the alternative was
real and the reasoning should survive the PR.

## When to write one

Write an ADR when:
- You chose one technology, library, or pattern over a concrete alternative.
- You made a tradeoff that will constrain future work (performance vs simplicity,
  consistency vs availability, etc.).
- You deviated from the spec or from a previous ADR.
- You rejected an approach that looks attractive so the team doesn't re-litigate
  it later.
- Future-you, reading a git blame six months from now, would ask "huh, why?"

Do **not** write an ADR for: implementation details obvious from the code,
stylistic choices already covered by the linter, or work that implements a
decision already recorded.

## Workflow

### 1. Pick the next sequence number
```bash
ls docs/decisions/ | grep -E '^[0-9]{4}-' | tail -1
```
Increment by one, zero-padded to four digits (e.g. `0003` → `0004`).

### 2. Choose a slug
Short, lowercase, hyphenated title: `use-sqlite-wal-mode`, `reject-celery`,
`model-abstraction-layer`. The file will be `docs/decisions/NNNN-slug.md`.

### 3. Fill in the template
Copy `templates/adr.template.md` to `docs/decisions/NNNN-slug.md` and replace
every `<placeholder>`:

- **Context** — the situation that forced a decision; constraints in play.
- **Decision** — what you chose, in one clear sentence.
- **Options considered** — at least two, with honest pros/cons for each.
  Include the option you *rejected* — that's often the most valuable part.
- **Consequences** — what becomes easier, what becomes harder, what is now
  locked in.
- **Related** — the spec section it implements or diverges from (`spec_v3.md
  §N`), any follow-up IDs (`docs/followups.md`), and the PR that introduced it.

Set **Status** to `proposed` until the PR is merged, then `accepted`.

### 4. Cross-link
In the same PR:
- Cite the ADR path in the PR description.
- If it implements a spec section, add a note in that section's prose or a
  cross-reference comment.
- If it opens a follow-up, append an entry to `docs/followups.md` referencing
  the ADR ID.

### 5. Superseding an ADR
If a future decision overturns this one, mark the old ADR `superseded by
NNNN-new-slug.md` and write a new ADR explaining the reversal. Never delete
an old ADR — the rejection history is the point.

## Output

```
## ADR Created

- Path:    docs/decisions/<NNNN-slug>.md
- Status:  proposed → accepted on merge
- Summary: <one sentence: what was decided and why>
- Related: <spec §N | follow-up ID | PR #N>
```
