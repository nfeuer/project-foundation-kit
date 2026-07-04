# Flaky Test Registry

This file is a **loan register**, not a graveyard. Every row represents a test that
has been temporarily quarantined from the gating suite so it stops burning CI time —
but it is still tracked, still owned, and still expected to be fixed. The loan
comes due.

`nightly-audit` reads this file and reports:
- Total quarantined count
- Any test quarantined for more than 30 days without a resolved follow-up

Do not delete rows. When a test is fixed, update the Follow-up ID to
`✅ RESOLVED <YYYY-MM-DD>` and remove the pytest marker from the source. The
follow-up entry moves to `followups-archive.md` via the `followup-tracking`
lifecycle.

---

| Test node id | Pass rate | First seen | Quarantined? | Follow-up ID | Owner |
|---|---|---|---|---|---|
| `tests/example/test_placeholder.py::test_example` | `3/5 (60%)` | `2026-01-01` | No | `FLAKY-example-placeholder` | — |

<!-- Add new rows above this line. One row per test node id. -->
<!-- Run the `flaky-triage` skill to generate rows — do not hand-edit pass rates. -->
