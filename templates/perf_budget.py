"""Runtime performance budget guardrail.

Measures elapsed wall-clock time for named operations and emits a structured
warning when an operation exceeds its configured budget. Feeds the same
observability pipeline as the cost guard and fallback alerts, so a single
Loki/Grafana alert rule covers both cost overruns and latency regressions.

Key ideas, in order of importance:

1. **Instrument every hot path, not just the slow ones.** The context manager
   adds negligible overhead; wrap all external/model calls and critical DB paths
   so regressions surface immediately in the ``invocation_log`` stream — where
   the **perf-budget** PR gate reads them.

2. **Config-driven budgets, never hardcoded.** Each path's p95 budget (ms) lives
   in a config dict loaded from YAML (``capabilities.perf.budgets``).
   ``PerfBudget`` has no opinion about what the numbers should be; it reads them
   from the dict the caller injects at construction time.

3. **Warn on exceed, never block.** A latency overage is a signal, not a stop
   condition. ``perf_budget`` emits a structured ``perf_budget_exceeded`` warning
   that the observability pipeline picks up, while leaving the call path
   unchanged. The **perf-budget** PR gate (a pre-PR skill) is where regressions
   are blocked before they ship.

Usage:

    # Load budgets from YAML config (capabilities.perf.budgets):
    budgets = {
        "llm.chat_completion": 2000.0,   # p95 budget in ms
        "db.task_list": 50.0,
        "db.task_write": 30.0,
    }
    pf = PerfBudget(budgets=budgets, alert_fn=notify)

    # As an async context manager:
    async with pf.measure("llm.chat_completion"):
        result = await call_model(...)

    # As a decorator on an async function:
    @pf.measure("db.task_list")
    async def list_tasks(user_id: int) -> list[Task]:
        ...

    # One-off, when you already know the budget:
    async with perf_budget("ad_hoc_path", budget_ms=100.0):
        result = await some_call()
"""

from __future__ import annotations

import functools
import time
from typing import Any, Awaitable, Callable, Protocol

import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------


class PerfBudgetExceededError(Exception):
    """Raised by callers that choose to treat a latency overage as fatal.

    ``perf_budget`` itself only warns; raise this from application code when
    a hard deadline must be enforced (e.g. an SLA-bound request path).

    Attributes:
        operation: The name of the timed operation.
        elapsed_ms: Actual elapsed time in milliseconds.
        budget_ms: The budget that was exceeded.
    """

    def __init__(
        self, operation: str, *, elapsed_ms: float, budget_ms: float
    ) -> None:
        super().__init__(
            f"{operation} took {elapsed_ms:.0f} ms (budget: {budget_ms:.0f} ms)"
        )
        self.operation = operation
        self.elapsed_ms = elapsed_ms
        self.budget_ms = budget_ms


# ---------------------------------------------------------------------------
# Pluggable alert interface
# ---------------------------------------------------------------------------


class AlertFn(Protocol):
    """Async callable for delivering a latency-budget alert.

    The simplest alerting interface: the caller provides this, the guard
    doesn't care whether it dispatches to Discord, Slack, or a test stub.
    Must accept keyword arguments ``component``, ``message``, and ``context``.
    """

    async def __call__(
        self,
        *,
        component: str,
        message: str,
        context: dict[str, Any],
    ) -> None: ...


# ---------------------------------------------------------------------------
# perf_budget — primitive context manager and decorator
# ---------------------------------------------------------------------------


class perf_budget:
    """Async context manager and decorator that enforces a per-operation latency budget.

    Times the wrapped block using ``time.monotonic()``. When elapsed time
    exceeds ``budget_ms``, emits a structured ``perf_budget_exceeded`` warning
    through structlog and, optionally, dispatches an alert via ``alert_fn``.
    The call always completes — the guard never raises on overage.

    Can be used in three ways::

        # 1. Inline context manager
        async with perf_budget("llm.complete", 2000.0):
            ...

        # 2. Decorator on an async function
        @perf_budget("db.read", 50.0)
        async def read_row(id: int) -> Row:
            ...

        # 3. Via PerfBudget (config-driven, preferred in application code)
        async with pf.measure("db.read"):
            ...

    Args:
        name: Logical operation name (matches a key in ``capabilities.perf.budgets``).
        budget_ms: Maximum acceptable elapsed time in milliseconds.
        alert_fn: Optional async callable for delivering alerts. Must match the
            ``AlertFn`` protocol. Never called when no overage occurs.
    """

    def __init__(
        self,
        name: str,
        budget_ms: float,
        *,
        alert_fn: AlertFn | None = None,
    ) -> None:
        self._name = name
        self._budget_ms = budget_ms
        self._alert_fn = alert_fn
        self._start: float = 0.0

    async def __aenter__(self) -> perf_budget:
        """Record the start time.

        Returns:
            This context manager instance.
        """
        self._start = time.monotonic()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Compute elapsed time and warn if the budget was exceeded.

        Always returns ``None`` (does not suppress exceptions).
        """
        elapsed_ms = (time.monotonic() - self._start) * 1000.0
        if elapsed_ms > self._budget_ms:
            logger.warning(
                "perf_budget_exceeded",
                event_type="perf_budget_exceeded",
                operation=self._name,
                elapsed_ms=round(elapsed_ms, 1),
                budget_ms=self._budget_ms,
            )
            if self._alert_fn is not None:
                try:
                    await self._alert_fn(
                        component="perf_budget",
                        message=(
                            f"{self._name} took {elapsed_ms:.0f} ms "
                            f"(budget: {self._budget_ms:.0f} ms)"
                        ),
                        context={
                            "operation": self._name,
                            "elapsed_ms": elapsed_ms,
                            "budget_ms": self._budget_ms,
                        },
                    )
                except Exception:
                    logger.exception(
                        "perf_budget.alert_dispatch_failed",
                        component="perf_budget",
                        operation=self._name,
                    )

    def __call__(
        self, func: Callable[..., Awaitable[Any]]
    ) -> Callable[..., Awaitable[Any]]:
        """Wrap an async function so every call is timed against this budget.

        A fresh timing context is created on each call, so the decorated
        function can be called concurrently without shared mutable state.

        Args:
            func: The async function to wrap. Must be a coroutine function.

        Returns:
            A new async function with an identical signature that times each
            invocation and warns on overage.
        """
        name = self._name
        budget_ms = self._budget_ms
        alert_fn = self._alert_fn

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with perf_budget(name, budget_ms, alert_fn=alert_fn):
                return await func(*args, **kwargs)

        return wrapper


# ---------------------------------------------------------------------------
# PerfBudget — config-driven wrapper (preferred in application code)
# ---------------------------------------------------------------------------


class PerfBudget:
    """Config-driven performance budget checker.

    Reads per-operation budgets from an injected dict (loaded from
    ``capabilities.perf.budgets`` in ``kit.yaml``) and returns a
    ``perf_budget`` context manager / decorator for each named operation.
    Callers never hardcode budget values; the config is the single source
    of truth for both this runtime guard and the **perf-budget** PR gate.

    Args:
        budgets: Dict mapping operation name to p95 budget in milliseconds.
            Matches the structure of ``capabilities.perf.budgets`` in
            ``.claude/kit.yaml``. Operations not in the dict are measured
            with an infinite budget (no warning emitted).
        alert_fn: Optional async callable for delivering alerts when a budget
            is exceeded. Must match the ``AlertFn`` protocol.

    Example::

        config = load_yaml(".claude/kit.yaml")
        pf = PerfBudget(
            budgets=config["capabilities"]["perf"]["budgets"],
            alert_fn=dispatch_fallback_alert,
        )

        async with pf.measure("llm.chat_completion"):
            response = await complete(prompt, schema, model_alias)
    """

    def __init__(
        self,
        budgets: dict[str, float],
        *,
        alert_fn: AlertFn | None = None,
    ) -> None:
        self._budgets = budgets
        self._alert_fn = alert_fn

    def measure(self, name: str) -> perf_budget:
        """Return a context manager / decorator for the named operation.

        Looks up ``name`` in the injected budget dict. If the operation is
        not present, the budget is ``float("inf")`` and no warning is ever
        emitted — the call is still timed, but silently.

        Args:
            name: Logical operation name (e.g. ``"llm.chat_completion"``).
                Should match a key in ``capabilities.perf.budgets``.

        Returns:
            A ``perf_budget`` instance usable as ``async with`` or as a
            function decorator.
        """
        budget_ms = self._budgets.get(name, float("inf"))
        return perf_budget(name, budget_ms, alert_fn=self._alert_fn)
