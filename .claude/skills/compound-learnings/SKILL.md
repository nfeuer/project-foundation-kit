---
name: compound-learnings
description: After solving a non-obvious problem — a gnarly bug, a tricky integration, a surprising workaround — write the solution pattern to docs/solutions/ so future planning and debugging start from it instead of re-deriving it. Each unit of work should make the next one easier.
cost: free
protects: "A hard-won fix to a tricky bug gets written down once, so the next person starts from the answer instead of repeating the same investigation."
requires: "capabilities.docs.enabled"
gate_key: capture
ci_job: none
---

# Compound Learnings

**Profile-driven.** Solutions live at `<docs.dir>/solutions/`, where `docs.dir`
is `capabilities.docs.dir` from `.claude/kit.yaml` (default: `docs`).

> **Mode.** This gate runs per `gates.modes.capture` in `.claude/kit.yaml`:
> `enforce` — run, block on failure; `suggest` — surface it at the natural
> moment with the `protects:` sentence and cost class above, run only on
> acceptance, and record accept/decline in the gate ledger
> (`.claude/scratch/gate-ledger.md`, SPEC.md §8.2) — never skip silently;
> `off` — not offered. Key absent → derive from `gates.strictness` per the
> table in `docs/PROFILE.md`. (SPEC.md §4.1, §4.4) The `capture` key is
> shared with followup-tracking and with doc-sync's follow-up logging;
> capture suggestions fire on materiality — a diff that touched docs, a
> debugging session worth writing down — not on every unit of work
> (SPEC.md §6.3).

A hard-won insight that lives only in one session's context is lost the moment
the session ends. This skill closes the loop the follow-ups log opens: where
`followup-tracking` captures *work still to do*, this captures *problems already
solved* — so the next task (and the next agent) starts from the answer, not the
investigation.

## When to run it

Run at the end of a unit of work whenever any of these happened:

- A bug took **real investigation** to root-cause (roughly: more than ~30
  minutes, or more than one wrong hypothesis).
- You discovered a **non-obvious constraint** of a dependency, API, or tool —
  behavior its docs don't state or state misleadingly.
- You built a **workaround** whose reason-for-being is invisible from the code.
- You found the **fast path** through something the next agent would do the
  slow way (a build quirk, a test-environment trap, a flaky external service).

What does **not** belong: routine feature work, anything the project docs or
spec already cover (update those instead — `doc-sync`), and anything session-
specific with no future value. When in doubt, write it — a short entry that is
never needed costs less than a re-derived investigation.

## Entry format

One file per solution: `<docs.dir>/solutions/YYYY-MM-DD-<slug>.md`.

```markdown
# <Short title stating the problem, not the fix>

- **Date:** YYYY-MM-DD
- **Area:** <subsystem / dependency / tool>
- **Symptom:** <what you observed — error text, wrong behavior. Verbatim
  fragments help future grep.>

## Root cause
<What was actually wrong, in 2–5 sentences.>

## Solution
<What fixed it. Include the exact command / config / code pattern.>

## How to recognize it next time
<The tell-tale signature — the log line, the error class, the smell that should
trigger "check docs/solutions" instead of a fresh investigation.>
```

Keep the **Symptom** section verbatim-rich: future sessions find these entries
by grepping error text, so paste the real message, not a paraphrase.

## The read side — this is what makes it compound

Writing entries is half the loop. The other half:

- **Before planning or debugging**, grep the solutions directory for the area
  and any error text you are seeing:
  ```bash
  grep -ril "<error fragment or subsystem>" docs/solutions/ 2>/dev/null
  ```
  CLAUDE.md's "Before You Start a Task" list includes this step — keep it there.
- **On a hit**, read the entry before forming hypotheses. Confirm it still
  applies rather than assuming, but start from it.

## Lifecycle

- Entries are append-only history; do not rewrite them as understanding evolves
  — add a new entry that supersedes and link the old one.
- When a solution graduates into real documentation (a docs page, a spec
  section, a code comment at the site), update those via `doc-sync` and note
  the promotion at the top of the entry. Leave the entry in place — its symptom
  text is still the search key.
- If the directory grows past ~50 entries, split by area subdirectory; never
  archive entries whose symptoms can still occur.

## Output

```
## Compound Learnings

- Added: <docs/solutions/YYYY-MM-DD-<slug>.md — title / none this unit of work>
- Superseded: <entry link / none>
- Promoted to docs/spec: <where / none>
```
