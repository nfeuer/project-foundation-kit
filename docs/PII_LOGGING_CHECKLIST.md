# PII Logging Checklist

Structured logs are queryable, indexed, and retained. A credential or PII value
logged once is exposed permanently. Apply this checklist to every new logging
call before it merges. The `observability-check` skill and `observability-reviewer`
agent both reference this file.

## Never log these

| Category | Examples | Why |
|---|---|---|
| Secrets / credentials | API keys, OAuth tokens, passwords, private keys, JWTs | Single log line = full compromise |
| Session tokens | Cookie values, session IDs, CSRF tokens | Replay attack vector |
| Full PII | Full name + email together, phone numbers, addresses, SSNs, DOB | Regulatory (GDPR / CCPA) |
| Message content | Full text of emails, SMS, chat messages | Often contains embedded PII |
| Model prompt payloads | System prompts with injected user data | May contain PII + proprietary content |
| Raw file contents | Any user-uploaded file logged in full | Unpredictable PII surface |

## What to log instead

**Identifiers** — log an opaque reference, not the value:
```python
# Bad
log.info("auth", token=bearer_token, email=user.email)

# Good
log.info("auth", user_id=user.id, token_prefix=bearer_token[:8] + "…")
```

**Counts and metadata** — log that a message exists, not what it says:
```python
# Bad
log.info("email_received", subject=msg.subject, body=msg.body)

# Good
log.info("email_received", message_id=msg.id, thread_id=msg.thread_id,
         subject_length=len(msg.subject), has_attachments=bool(msg.attachments))
```

**Hashed identifiers** — when you need to correlate across sessions without
storing the raw value, use a one-way hash:
```python
import hashlib
user_hash = hashlib.sha256(email.encode()).hexdigest()[:16]
log.info("user_action", user_hash=user_hash, action="login")
```

**Error context** — log the error type and message, not the full exception
stack if it contains user data:
```python
# Strip PII from exception messages before logging
log.error("parse_failed", error_type=type(e).__name__, field="email_address")
```

## Redaction rules

1. **Truncate tokens**: log at most the first 8 characters + `…` as a hint for
   debugging. Never log the full token.
2. **Hash emails/phones** when you need to correlate but not identify:
   SHA-256 prefix (first 16 hex chars) is enough to match rows.
3. **Omit body fields entirely** from structured logs. Log `body_bytes=N` if
   size matters.
4. **Sanitize model output** before logging it — model output may echo back
   user-supplied PII. Log `output_tokens=N` and `output_preview=output[:100]`
   only when debugging.
5. **Remove debug fields before merge** — temporary `log.debug("dump", data=...)`
   calls must not reach main. The `pre-pr` secrets scan catches raw keys; you
   must manually audit PII fields.

## Retention discipline

- Logs containing any PII reference (even a hashed ID) should be subject to
  your data retention policy — define the window in your observability config
  (e.g. Loki `retention_period`).
- Do not write PII to `DEBUG`-level logs that ship to production — debug logs
  are often retained indefinitely and excluded from retention sweeps.
- Anonymize or delete logs for a user on account deletion. Design your log
  schema so user records are queryable by `user_id` for this purpose.

## How this pairs with structured-logging templates

The project's `templates/logging_setup.py` configures a structlog pipeline that:
- Strips any field whose key matches `_SENSITIVE_KEYS` (a configurable set:
  `password`, `token`, `secret`, `key`, `authorization`).
- Truncates field values longer than `MAX_FIELD_LEN` bytes in production.
- Applies the `censor_processor` before any renderer.

Extend `_SENSITIVE_KEYS` rather than adding manual redaction in call sites.
If a field can't be expressed safely under these constraints, it belongs in a
dedicated audit log with stricter access control, not the main structured log.

## Quick checklist (per logging call)

- [ ] No secret, token, or password in any field value
- [ ] No full email address, name+email pair, phone, or address
- [ ] No message body or model prompt payload
- [ ] Identifiers are opaque references (IDs, hashes) not raw user input
- [ ] Debug dump fields removed before merge
- [ ] Field names are unambiguous — avoid generic `data=`, `payload=`, `content=`
