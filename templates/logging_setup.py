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

Usage:
    setup_logging(log_level="INFO", json_output=not sys.stdout.isatty())
    log = structlog.get_logger()
    bind_request_context(correlation_id="abc123", user_id="nick")
    log.info("task_completed", event_type="task.completed", task_id=42, latency_ms=88)
"""

from __future__ import annotations

import contextvars
import logging
import sys
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
