"""Structured logging setup — machine-parseable in prod, human-readable in dev.

Reference implementation extracted from a production asyncio service. The key
ideas, in order of importance:

1. **One processor chain, two renderers.** The same fields are emitted whether
   you render JSON (prod, for Loki/Datadog to parse) or a colorized console
   line (local dev, for a human to read). Flip a single boolean at startup — you
   never lose field coverage by switching modes.

2. **Context vars carry correlation IDs automatically.** Set `correlation_id`,
   `user_id`, etc. once at the top of a request/interaction and every nested log
   line downstream inherits them without threading them through call signatures.

3. **Event names are snake_case verbs/nouns, not sentences.** `logger.info(
   "task_completed", task_id=...)` — not `logger.info("The task completed")`.
   High-value events also carry a namespaced ``event_type`` (e.g.
   ``"cost.budget_exceeded"``) that your log pipeline can promote to an indexed
   label for cheap filtering.

4. **Every significant operation logs outcome + duration — not only API/model
   calls.** Background jobs, batch stages, cache rebuilds, migrations, file
   exports: anything that can be slow or can fail gets a paired
   ``<name>_completed`` / ``<name>_failed`` event with ``duration_ms``. The
   ``log_operation`` context manager below makes the pair a one-liner. The full
   per-process-type event catalog lives in ``docs/LOGGING_STANDARD.md``.

Usage:
    setup_logging(log_level="INFO", json_output=not sys.stdout.isatty())
    log = structlog.get_logger()
    bind_request_context(correlation_id="abc123", user_id="nick")
    log.info("task_completed", event_type="task.completed", task_id=42, latency_ms=88)

    with log_operation("nightly_export", job_id=run_id) as op:
        rows = export_batch()
        op["rows_written"] = len(rows)
    # → nightly_export_completed  duration_ms=1234.5 job_id=... rows_written=8812
    # (or nightly_export_failed with the traceback, then the exception re-raises)
"""

from __future__ import annotations

import contextvars
import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import structlog

# --- Context vars: set once per request/interaction, inherited by every log ---
correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="")
channel_var: contextvars.ContextVar[str] = contextvars.ContextVar("channel", default="")


def bind_request_context(
    *, correlation_id: str = "", user_id: str = "", channel: str = ""
) -> None:
    """Bind identifiers for the current async context. Call at request entry."""
    if correlation_id:
        correlation_id_var.set(correlation_id)
    if user_id:
        user_id_var.set(user_id)
    if channel:
        channel_var.set(channel)


def _add_context_vars(
    _logger: Any, _method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject non-empty context vars into every event dict."""
    for key, var in (
        ("correlation_id", correlation_id_var),
        ("user_id", user_id_var),
        ("channel", channel_var),
    ):
        value = var.get()
        if value:
            event_dict.setdefault(key, value)
    return event_dict


@contextmanager
def log_operation(name: str, **fields: Any) -> Iterator[dict[str, Any]]:
    """Log outcome + duration for any significant operation, not just API calls.

    Emits ``<name>_completed`` with ``duration_ms`` on success, or
    ``<name>_failed`` with ``duration_ms`` and the traceback on error (the
    exception re-raises — this records failures, it never swallows them).
    Mutate the yielded dict to attach result fields (row counts, items skipped)
    to the terminal event. Wrap background jobs, batch stages, cache rebuilds,
    migrations — anything that can be slow or can fail. See
    ``docs/LOGGING_STANDARD.md`` for the event catalog this pattern serves.

    Args:
        name: snake_case operation name; becomes the event-name prefix.
        **fields: identifying fields (job_id, batch_id, ...) attached to the
            terminal event.
    """
    log = structlog.get_logger()
    start = time.monotonic()
    result_fields: dict[str, Any] = {}
    try:
        yield result_fields
    except Exception:
        log.error(
            f"{name}_failed",
            duration_ms=round((time.monotonic() - start) * 1000, 1),
            **fields,
            **result_fields,
            exc_info=True,
        )
        raise
    log.info(
        f"{name}_completed",
        duration_ms=round((time.monotonic() - start) * 1000, 1),
        **fields,
        **result_fields,
    )


def setup_logging(log_level: str = "INFO", json_output: bool = True) -> None:
    """Configure structlog once at process startup.

    Args:
        log_level: Minimum level to emit (e.g. "INFO", "DEBUG").
        json_output: True → JSON lines (production, machine-parseable).
            False → colorized console (local dev, human-readable).
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_context_vars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[*shared_processors, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
