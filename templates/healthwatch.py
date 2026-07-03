"""Health-watcher sidecar — heartbeat file + transition-alert pattern.

Reference skeleton for a lightweight health-check loop that runs alongside
a deployed service. The key ideas, in order of importance:

1. **Atomic heartbeat file.** On every successful poll the watcher writes a
   UTC timestamp to a file via an atomic rename (write to ``.tmp``, then
   ``rename()``). The main app's ``/health`` endpoint reads the file and
   reports ``stale`` when the timestamp is older than a configurable threshold.
   This makes the watcher's liveness a *data dependency* of the health endpoint
   rather than a function call — the endpoint doesn't need to know the watcher
   exists, and the watcher doesn't need to know about the endpoint.

2. **Transition-alert, not poll-alert.** The alert callable fires only when
   health state changes (healthy → unhealthy or back), never on every poll.
   This keeps alert volume low while guaranteeing the first failure is always
   seen. A sustained outage produces exactly two alerts: down and recovery.

3. **Injected probe + alert.** Pass in a ``probe`` coroutine that calls your
   real health target (HTTP, socket, subprocess, queue depth — anything async).
   Pass in an ``alert_fn`` for notifications. The watcher owns the loop and the
   state machine; it has no opinion about transport or what "healthy" means.

Usage:

    import aiohttp, asyncio, pathlib

    async def http_probe() -> bool:
        try:
            async with aiohttp.ClientSession() as s:
                r = await s.get("http://localhost:8000/health", timeout=aiohttp.ClientTimeout(total=5))
                return r.status == 200
        except Exception:
            return False

    async def my_alert(*, component: str, message: str, **kw: object) -> None:
        ...  # post to Discord / PagerDuty / etc.

    cfg = HealthWatcherConfig(
        poll_interval_seconds=30,
        heartbeat_path=pathlib.Path("/run/donna/health.heartbeat"),
        stale_threshold_seconds=90,
    )
    watcher = HealthWatcher(config=cfg, probe=http_probe, alert_fn=my_alert)
    asyncio.run(watcher.run())

    # In the main app's /health handler:
    age = heartbeat_age_seconds(pathlib.Path("/run/donna/health.heartbeat"))
    if age is None or age > cfg.stale_threshold_seconds:
        return {"status": "stale", "heartbeat_age_seconds": age}
    return {"status": "ok"}
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
import enum
import pathlib
from typing import Awaitable, Callable

import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ProbeFn = Callable[[], Awaitable[bool]]
AlertFn = Callable[..., Awaitable[None]]


class HealthState(enum.Enum):
    """The watcher's view of the service's health."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


@dataclasses.dataclass(frozen=True)
class HealthWatcherConfig:
    """Configuration for the HealthWatcher loop.

    Attributes:
        poll_interval_seconds: How often to call the probe.
        heartbeat_path: File path the watcher writes on each healthy poll.
            The directory must exist and be writable.
        stale_threshold_seconds: Age (seconds) after which the main app should
            consider the heartbeat stale and report degraded health. Should be
            at least 2× poll_interval_seconds to avoid false positives.
        consecutive_failures_before_unhealthy: How many sequential probe
            failures to require before transitioning to UNHEALTHY. Avoids
            flapping on transient glitches.
    """

    poll_interval_seconds: float = 30.0
    heartbeat_path: pathlib.Path = pathlib.Path("/tmp/healthwatch.heartbeat")
    stale_threshold_seconds: float = 90.0
    consecutive_failures_before_unhealthy: int = 2


# ---------------------------------------------------------------------------
# Heartbeat helpers (used by both watcher and main app)
# ---------------------------------------------------------------------------


def heartbeat_age_seconds(path: pathlib.Path) -> float | None:
    """Return the age of the heartbeat file in seconds, or None if missing.

    Call this from your ``/health`` endpoint. Report ``stale`` if the returned
    value is ``None`` or exceeds ``stale_threshold_seconds``.

    Args:
        path: The same path passed to ``HealthWatcherConfig.heartbeat_path``.

    Returns:
        Seconds since the heartbeat was last written, or None if the file
        does not exist.
    """
    try:
        raw = path.read_text().strip()
        written = dt.datetime.fromisoformat(raw)
        now = dt.datetime.now(dt.timezone.utc)
        return (now - written).total_seconds()
    except (FileNotFoundError, ValueError):
        return None


def _write_heartbeat(path: pathlib.Path) -> None:
    """Atomically write the current UTC timestamp to the heartbeat file.

    Uses write-to-tmp + rename so readers never see a partial write.

    Args:
        path: Destination heartbeat file path.
    """
    tmp = path.with_suffix(".tmp")
    tmp.write_text(dt.datetime.now(dt.timezone.utc).isoformat())
    tmp.rename(path)  # atomic on POSIX; near-atomic on Windows


# ---------------------------------------------------------------------------
# HealthWatcher
# ---------------------------------------------------------------------------


class HealthWatcher:
    """Poll a probe on an interval, write heartbeats, and alert on transitions.

    Args:
        config: Timing and path configuration.
        probe: Async callable that returns True (healthy) or False (unhealthy).
            Must not raise; catch its own exceptions and return False on failure.
        alert_fn: Optional async callable invoked on state transitions. Receives
            keyword args ``component``, ``message``, ``previous_state``,
            ``new_state``, and ``context``. Never raises (errors are logged).
    """

    def __init__(
        self,
        *,
        config: HealthWatcherConfig,
        probe: ProbeFn,
        alert_fn: AlertFn | None = None,
    ) -> None:
        self._cfg = config
        self._probe = probe
        self._alert_fn = alert_fn
        self._state: HealthState = HealthState.UNKNOWN
        self._consecutive_failures: int = 0

    async def run(self) -> None:
        """Start the watch loop. Runs until the task is cancelled.

        Logs a ``healthwatcher.started`` event at startup and
        ``healthwatcher.stopped`` when cancelled. Use
        ``asyncio.create_task(watcher.run())`` to run alongside your service.
        """
        logger.info(
            "healthwatcher.started",
            event_type="healthwatcher.started",
            poll_interval=self._cfg.poll_interval_seconds,
            heartbeat_path=str(self._cfg.heartbeat_path),
        )
        try:
            while True:
                await self._tick()
                await asyncio.sleep(self._cfg.poll_interval_seconds)
        except asyncio.CancelledError:
            logger.info("healthwatcher.stopped", event_type="healthwatcher.stopped")
            raise

    async def _tick(self) -> None:
        """Execute one probe, update state, write heartbeat, and alert if needed."""
        healthy = await self._probe()

        if healthy:
            self._consecutive_failures = 0
            previous = self._state
            self._state = HealthState.HEALTHY
            try:
                _write_heartbeat(self._cfg.heartbeat_path)
            except OSError:
                logger.exception(
                    "healthwatcher.heartbeat_write_failed",
                    path=str(self._cfg.heartbeat_path),
                )
            if previous not in (HealthState.HEALTHY, HealthState.UNKNOWN):
                await self._alert(
                    previous_state=previous,
                    new_state=self._state,
                    message="Service recovered: probe is healthy again.",
                )
        else:
            self._consecutive_failures += 1
            logger.warning(
                "healthwatcher.probe_failed",
                event_type="healthwatcher.probe_failed",
                consecutive_failures=self._consecutive_failures,
                threshold=self._cfg.consecutive_failures_before_unhealthy,
            )
            if (
                self._consecutive_failures
                >= self._cfg.consecutive_failures_before_unhealthy
                and self._state != HealthState.UNHEALTHY
            ):
                previous = self._state
                self._state = HealthState.UNHEALTHY
                await self._alert(
                    previous_state=previous,
                    new_state=self._state,
                    message=(
                        f"Service unhealthy: {self._consecutive_failures} "
                        "consecutive probe failures."
                    ),
                )

    async def _alert(
        self,
        *,
        previous_state: HealthState,
        new_state: HealthState,
        message: str,
    ) -> None:
        """Dispatch a state-transition alert; log regardless of alert_fn.

        Args:
            previous_state: The state before this transition.
            new_state: The state after this transition.
            message: Human-readable summary for the alert body.
        """
        logger.warning(
            "healthwatcher.state_changed",
            event_type="healthwatcher.state_changed",
            previous_state=previous_state.value,
            new_state=new_state.value,
            message=message,
        )
        if self._alert_fn is None:
            return
        try:
            await self._alert_fn(
                component="healthwatcher",
                message=message,
                previous_state=previous_state.value,
                new_state=new_state.value,
                context={"heartbeat_path": str(self._cfg.heartbeat_path)},
            )
        except Exception:
            logger.exception(
                "healthwatcher.alert_dispatch_failed",
                component="healthwatcher",
            )
