# Incident: <COMPONENT> — <YYYY-MM-DD>

<!-- One sentence: what broke, in what component, first detected when. -->
**Summary:** <SUMMARY>

---

## Trigger

<!-- The machine-readable event that opened this note. -->
| Field       | Value                       |
|-------------|---------------------------  |
| event_type  | `<EVENT_TYPE>`              |
| component   | `<COMPONENT>`               |
| count       | <COUNT> in <WINDOW>         |
| first seen  | <FIRST_TIMESTAMP> UTC       |
| detected at | <INCIDENT_TIMESTAMP> UTC    |

## Impact

<!-- What is currently degraded or unavailable? Who is affected? -->
<IMPACT>

<!-- If unknown at time of opening, write: "Assessing — update within 15 min." -->

## Timeline

<!-- Add entries as the incident unfolds. Keep UTC timestamps. -->
| Time (UTC)          | Event                                      |
|---------------------|--------------------------------------------|
| <FIRST_TIMESTAMP>   | First `<EVENT_TYPE>` logged for component  |
| <INCIDENT_TIMESTAMP>| Incident note auto-opened by incident-capture |
| <TIMESTAMP>         | <ACTION OR OBSERVATION>                    |

## Correlated Logs

<!-- Paste the key log lines (correlation_id, error, fallback taken).
     Keep to ≤20 lines; link to full Loki/log query for the rest. -->
```
<CORRELATION_LOG_LINES>
```

<!-- Loki query that reproduces this window: -->
<!-- {app="<APP>"} |= "<EVENT_TYPE>" | json | component="<COMPONENT>" -->

Correlation IDs: `<CORRELATION_IDS>`

## Suspected Cause

<!-- First hypothesis. Mark clearly if speculative. Update as you learn more. -->
<SUSPECTED_CAUSE>

<!-- Tip: check Related Commits first — a recent change touching this component
     is the highest-probability culprit. -->

## Related Commits

<!-- Output of: git log --oneline -10 -- src/<pkg>/<component>/ config/<component>*.yaml -->
```
<GIT_LOG_LINES>
```

## Mitigation Taken

<!-- What has been done so far to reduce impact or restore service? -->
- [ ] <ACTION>

<!-- Leave unchecked until complete. Add timestamp when checked off. -->

## Follow-ups

<!-- Reference docs/followups.md IDs for any deferred work this incident reveals.
     Add entries via the followup-tracking skill before closing this note. -->
- <FOLLOWUP_ID> — <short title>

## Status

<!-- Update this field as the incident progresses. -->
**Status:** OPEN | MITIGATED | RESOLVED

<!-- OPEN      — impact ongoing, no fix in place
     MITIGATED — impact reduced or contained, root cause not yet fixed
     RESOLVED  — service restored; root cause addressed or accepted
     Add resolved timestamp and rename file to <slug>-resolved.md on close. -->

**Resolved at:** <RESOLVED_TIMESTAMP> UTC  *(fill in when closed)*
**Resolution:** <RESOLUTION_SUMMARY>
