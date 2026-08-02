# Scheduled check-ins bill the whole session, and a 60-minute interval is the worst one

- **Date:** 2026-08-02
- **Area:** PR watching / `send_later` + cron check-ins / model routing
- **Symptom:** A week's model budget consumed by ~20 hourly "is the PR merged
  yet?" check-ins on a PR that was green, conflict-free, and awaiting a human
  from the first check onward. The status call itself is one trivial API
  request, so the spend looks impossible for the work performed.

## Root cause

Three multipliers, none of them the status check:

1. **A self-bound check-in re-sends the entire session.** The Routine fires
   into the existing session, so every firing re-submits the whole accumulated
   conversation — audit output, plan docs, diffs, prior tool results — as input
   tokens. Cost scales with how much work the session has already done, not
   with the check.
2. **It inherits that session's model.** A Routine bound to a persistent
   session (self-bind or `persistent_session_id`) runs on the session's model
   until the binding clears. A heartbeat parked in a Fable-tier session bills
   the full conversation at Fable rates, every time; there is no cheaper path
   without changing the binding.
3. **60 minutes lands exactly on the prompt-cache cliff.** The cache TTL is one
   hour, so an hourly poll arrives at or just past expiry and pays full-price
   input on the whole prefix instead of the ~0.1× cache-read rate. **A
   45-minute interval costs less in total than a 60-minute one** despite firing
   more often.

Compounding it: the webhook subscription already delivered both CI success and
the merge. The polling was pure belt-and-braces and caught nothing in ~20
firings.

## Solution

- **Poll only for something you own.** Red CI you are fixing, a conflict you
  are resolving. A green, clean, review-free PR waiting on a human needs zero
  polling — the human is the event source, and the webhook covers the merge.
- **Never bind a recurring check to a working session.** If a check-in is
  genuinely needed, fire it into a fresh session (`create_new_session_on_fire`)
  pinned to `models.mechanical`: ~2k tokens at Haiku rates instead of the whole
  conversation at whatever the session runs on.
- **Back off and cap.** 1h → 2h → 4h → 8h, stopping after ~3 quiet checks or 24
  hours. A quiet PR gets quieter, not busier.
- **Never pick a flat 60 minutes** for anything that re-sends a large prefix.
  Go under the TTL (45m) to stay cached, or well over it (4h+) so the cache was
  never going to help and the firing count is low.

## How to recognize it next time

Spend that scales with session age rather than with work done — a cheap,
repetitive action costing more each time it runs. Check whether the recurring
step is bound to a long session (`persist_session: true` with a
`persistent_session_id`), and whether its interval sits within a few minutes of
60. Either alone is expensive; together they multiply.
