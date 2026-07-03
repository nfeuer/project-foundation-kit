"""Pre-call budget guardrail for metered external APIs.

Reference implementation for any service that bills per call and needs to
stop before it overspends. The key ideas, in order of importance:

1. **Log every call, check before every call.** Spend is recorded in an
   ``invocation_log`` table on *every* API call (task_type, model_alias,
   tokens_in, tokens_out, cost_usd, timestamp). ``BudgetGuard.check()``
   reads that table *before* each new call, so every metered request is
   gated — not sampled, not approximated.

2. **Config-driven thresholds, never hardcoded.** Daily limit, monthly limit,
   and the warning fraction live in a config dict the caller loads from YAML.
   The guard has no opinion about what the numbers should be.

3. **Two-tier alert: warn once at 90%, raise at 100%.** A single warning fires
   at ``warn_fraction`` of the monthly limit (default 90%), exactly once per
   guard instance. At or above the hard limit, ``BudgetPausedError`` is raised
   and the caller decides the degraded path. The guard never decides that.

Usage:

    # Wire up an async scalar query for your DB (aiosqlite example):
    import aiosqlite

    async def fetch_scalar(sql: str, params: tuple = ()) -> float | None:
        async with aiosqlite.connect("donna_tasks.db") as db:
            async with db.execute(sql, params) as cur:
                row = await cur.fetchone()
                return float(row[0]) if row and row[0] is not None else None

    config = {
        "daily_limit_usd": 20.0,
        "monthly_limit_usd": 100.0,
        "warn_fraction": 0.9,
    }
    tracker = CostTracker(fetch_scalar)
    guard = BudgetGuard(tracker, config=config, alert_fn=notify)

    # Before every metered call:
    await guard.check()               # raises BudgetPausedError if over limit
    result = await call_api(...)
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Callable, Awaitable, Protocol

import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------


class BudgetPausedError(Exception):
    """Raised by BudgetGuard.check() when a spend limit has been reached.

    Attributes:
        reason: Human-readable explanation (e.g. "daily limit reached").
        spent: Current spend amount that triggered the pause.
        limit: The threshold that was crossed.
    """

    def __init__(self, reason: str, *, spent: float, limit: float) -> None:
        super().__init__(reason)
        self.reason = reason
        self.spent = spent
        self.limit = limit


# ---------------------------------------------------------------------------
# Pluggable async query interface
# ---------------------------------------------------------------------------


class FetchScalar(Protocol):
    """Async function that executes a SQL query and returns one float value.

    The simplest DB-agnostic interface: the caller provides this, the guard
    doesn't care whether it's aiosqlite, asyncpg, or an in-memory stub.
    Returns None when the query produces no rows (interpreted as 0.0 spend).
    """

    async def __call__(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> float | None: ...


AlertFn = Callable[..., Awaitable[None]]

# ---------------------------------------------------------------------------
# CostTracker — reads spend from the invocation log
# ---------------------------------------------------------------------------

_SQL_DAILY = """
    SELECT COALESCE(SUM(cost_usd), 0.0)
    FROM invocation_log
    WHERE date(timestamp) = date('now')
"""

_SQL_MONTHLY = """
    SELECT COALESCE(SUM(cost_usd), 0.0)
    FROM invocation_log
    WHERE timestamp >= date('now', 'start of month')
"""

_SQL_AVG_DAILY_7D = """
    SELECT COALESCE(SUM(cost_usd), 0.0) / 7.0
    FROM invocation_log
    WHERE timestamp >= date('now', '-6 days')
"""

_SQL_DAYS_LEFT = """
    SELECT
      CAST(strftime('%d', date('now','start of month','+1 month','-1 day')) AS INTEGER)
      - CAST(strftime('%d', date('now')) AS INTEGER)
"""


class CostTracker:
    """Queries the invocation_log for current and projected spend.

    Args:
        fetch: An async function matching the ``FetchScalar`` protocol.
            Wrap your DB connection here; the tracker stays DB-agnostic.

    All query methods catch exceptions and return 0.0 on failure, so a DB
    hiccup doesn't prevent the guard from running (it errs on the side of
    allowing the call rather than false-pausing on a read error).
    """

    def __init__(self, fetch: FetchScalar) -> None:
        self._fetch = fetch

    async def daily_total(self) -> float:
        """Return total spend so far today (UTC date).

        Returns:
            Sum of cost_usd for rows where date(timestamp) = today, or 0.0.
        """
        try:
            return (await self._fetch(_SQL_DAILY)) or 0.0
        except Exception:
            logger.exception("cost_tracker.daily_total_failed")
            return 0.0

    async def monthly_total(self) -> float:
        """Return month-to-date spend.

        Returns:
            Sum of cost_usd since the start of the current calendar month, or 0.0.
        """
        try:
            return (await self._fetch(_SQL_MONTHLY)) or 0.0
        except Exception:
            logger.exception("cost_tracker.monthly_total_failed")
            return 0.0

    async def rolling_avg_daily(self) -> float:
        """Return the 7-day rolling average daily spend.

        Returns:
            Total cost_usd over the last 7 days divided by 7, or 0.0.
        """
        try:
            return (await self._fetch(_SQL_AVG_DAILY_7D)) or 0.0
        except Exception:
            logger.exception("cost_tracker.rolling_avg_failed")
            return 0.0

    async def projected_monthly(self) -> float:
        """Return a projected end-of-month spend based on MTD + rolling average.

        Computes: month_to_date + (avg_daily_7d * days_remaining_in_month).

        Returns:
            Estimated total spend by end of month, or the MTD total if the
            days-remaining query fails.
        """
        try:
            mtd = await self.monthly_total()
            avg = await self.rolling_avg_daily()
            days_left = (await self._fetch(_SQL_DAYS_LEFT)) or 0.0
            return mtd + avg * days_left
        except Exception:
            logger.exception("cost_tracker.projection_failed")
            return await self.monthly_total()


# ---------------------------------------------------------------------------
# BudgetGuard — async pre-call gate
# ---------------------------------------------------------------------------


class BudgetGuard:
    """Async pre-call gate that raises BudgetPausedError when limits are hit.

    Call ``await guard.check()`` before every metered API call. The guard
    checks daily spend (hard limit) and monthly spend (hard limit), and emits
    a one-shot warning at ``warn_fraction`` of the monthly limit.

    Args:
        tracker: A ``CostTracker`` (or compatible object) for reading spend.
        config: Dict with keys ``daily_limit_usd``, ``monthly_limit_usd``, and
            optionally ``warn_fraction`` (default 0.9).
        alert_fn: Optional async callable for delivering warn/pause alerts
            (e.g. Discord dispatch). Must accept keyword args ``component``,
            ``message``, and ``context``. Never called on the raise path —
            only on the warn path.
    """

    def __init__(
        self,
        tracker: CostTracker,
        *,
        config: dict[str, Any],
        alert_fn: AlertFn | None = None,
    ) -> None:
        self._tracker = tracker
        self._daily_limit: float = float(config["daily_limit_usd"])
        self._monthly_limit: float = float(config["monthly_limit_usd"])
        self._warn_fraction: float = float(config.get("warn_fraction", 0.9))
        self._alert_fn = alert_fn
        self._monthly_warned: bool = False  # fire the 90% warning once per instance

    async def check(self) -> None:
        """Assert that neither daily nor monthly spend has reached its limit.

        Call this before every metered external API call.

        Raises:
            BudgetPausedError: If today's spend >= daily_limit_usd, or if
                month-to-date spend >= monthly_limit_usd.
        """
        now = dt.datetime.now(dt.timezone.utc)
        daily = await self._tracker.daily_total()
        monthly = await self._tracker.monthly_total()

        # --- Hard pause: daily limit ---
        if daily >= self._daily_limit:
            logger.warning(
                "budget.daily_limit_reached",
                event_type="budget.paused",
                daily_spent=daily,
                daily_limit=self._daily_limit,
                timestamp=now.isoformat(),
            )
            raise BudgetPausedError(
                "daily limit reached",
                spent=daily,
                limit=self._daily_limit,
            )

        # --- Hard pause: monthly limit ---
        if monthly >= self._monthly_limit:
            logger.warning(
                "budget.monthly_limit_reached",
                event_type="budget.paused",
                monthly_spent=monthly,
                monthly_limit=self._monthly_limit,
                timestamp=now.isoformat(),
            )
            raise BudgetPausedError(
                "monthly limit reached",
                spent=monthly,
                limit=self._monthly_limit,
            )

        # --- Soft warn: approaching monthly limit (one-shot) ---
        warn_threshold = self._monthly_limit * self._warn_fraction
        if not self._monthly_warned and monthly >= warn_threshold:
            self._monthly_warned = True
            logger.warning(
                "budget.monthly_warn",
                event_type="budget.warn",
                monthly_spent=monthly,
                warn_threshold=warn_threshold,
                monthly_limit=self._monthly_limit,
                timestamp=now.isoformat(),
            )
            if self._alert_fn is not None:
                try:
                    await self._alert_fn(
                        component="budget_guard",
                        message=(
                            f"Monthly API spend at ${monthly:.2f} "
                            f"({monthly / self._monthly_limit:.0%} of "
                            f"${self._monthly_limit:.2f} limit)"
                        ),
                        context={
                            "monthly_spent": monthly,
                            "monthly_limit": self._monthly_limit,
                        },
                    )
                except Exception:
                    logger.exception(
                        "budget_guard.alert_dispatch_failed",
                        component="budget_guard",
                    )
