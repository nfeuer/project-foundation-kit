"""No-silent-failure fallback alerting.

The rule this enforces: every ``try/except`` that falls back to a default or a
degraded path must make that fallback *observable*. A swallowed exception is a
bug that will cost you hours at 2am. Never write ``contextlib.suppress(
Exception)`` around a real operation.

Three tiers, in priority order:

1. **Always log** an ``event_type="fallback_activated"`` line — this works even
   when no notifier is wired, so observability never depends on infra being up.
2. **Notify a debug channel** (Discord/Slack/PagerDuty) when one is available,
   rate-limited so a flapping component can't spam you.
3. **Never raise from the alert path.** Alerting failures are logged, not
   propagated — the fallback must not be made worse by a broken alerter.

Usage in a component:

    try:
        data = await primary_source.read()
    except SourceError as exc:
        await emit_fallback_alert(
            self._alert_fn,                       # may be None
            component="calendar_sync",
            error=str(exc),
            fallback="using last cached snapshot",
            context={"user_id": user_id},
        )
        data = cached_snapshot
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Protocol

import structlog

logger = structlog.get_logger()


class FallbackAlert(Protocol):
    """The notifier callable a service exposes (e.g. Discord/Slack dispatch)."""

    async def __call__(
        self,
        *,
        component: str,
        error: str,
        fallback: str,
        context: dict[str, Any] | None = None,
        cooldown_seconds: int = 3600,
    ) -> None: ...


async def emit_fallback_alert(
    alert_fn: FallbackAlert | None,
    *,
    component: str,
    error: str,
    fallback: str,
    context: dict[str, Any] | None = None,
    cooldown_seconds: int = 3600,
) -> None:
    """Log a fallback unconditionally, then dispatch to a notifier if present.

    Args:
        alert_fn: The notifier to dispatch to, or None (log-only is still valid).
        component: Stable name of the subsystem that fell back.
        error: What went wrong (the caught exception, stringified).
        fallback: What the code did instead — the degraded behavior.
        context: Extra structured fields (ids, counts) for the log + alert.
        cooldown_seconds: Dedup window so a flapping component can't spam.
    """
    # Tier 1: always log, no notifier required.
    logger.warning(
        "fallback_activated",
        event_type="fallback_activated",
        component=component,
        error=error,
        fallback=fallback,
        **(context or {}),
    )
    if alert_fn is None:
        return
    # Tier 2 + 3: dispatch, but never let the alert path raise.
    try:
        await alert_fn(
            component=component,
            error=error,
            fallback=fallback,
            context=context,
            cooldown_seconds=cooldown_seconds,
        )
    except Exception:
        logger.exception("fallback_alert_dispatch_failed", component=component)


class FallbackNotifier:
    """A concrete notifier with dedup + recursion guard.

    Wire one of these to your chat/paging backend and pass ``.dispatch`` as the
    ``alert_fn`` above. The dedup key is ``(component, error[:50])`` so repeated
    identical failures within the cooldown window are logged but not re-sent.
    """

    def __init__(self, send_to_debug_channel: Any) -> None:
        self._send = send_to_debug_channel
        self._history: dict[tuple[str, str], dt.datetime] = {}
        self._alerting = False  # recursion guard: alerting can't trigger alerts

    async def dispatch(
        self,
        *,
        component: str,
        error: str,
        fallback: str,
        context: dict[str, Any] | None = None,
        cooldown_seconds: int = 3600,
        now: dt.datetime | None = None,
    ) -> bool:
        now = now or dt.datetime.now(dt.timezone.utc)
        key = (component, error[:50])
        last = self._history.get(key)
        if last and (now - last).total_seconds() < cooldown_seconds:
            return False
        if self._alerting:
            return False
        self._alerting = True
        try:
            message = (
                f"**Fallback activated** in `{component}`\n"
                f"**Error:** {error}\n**Fallback:** {fallback}"
            )
            await self._send(message)
            self._history[key] = now
            return True
        finally:
            self._alerting = False
