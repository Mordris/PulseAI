"""Structured logs for collection: JSON for machines or a console view for people, on stderr."""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.typing import Processor


def _stderr_logger(*_args: object) -> structlog.PrintLogger:
    """A logger on the current stderr, so a stream swapped in later (as in tests) is used."""
    return structlog.PrintLogger(sys.stderr)


def configure_logging(*, json: bool, verbose: bool) -> None:
    """Send structlog events to stderr: DEBUG and up when verbose, WARNING and up otherwise.

    Tracebacks are plain, without local variables: a frame can hold an auth header value, and
    the console renderer's default (rich) prints locals.
    """
    renderers: list[Processor] = (
        [structlog.processors.format_exc_info, structlog.processors.JSONRenderer()]
        if json
        else [
            structlog.dev.ConsoleRenderer(
                colors=sys.stderr.isatty(), exception_formatter=structlog.dev.plain_traceback
            )
        ]
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            *renderers,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if verbose else logging.WARNING
        ),
        logger_factory=_stderr_logger,
        cache_logger_on_first_use=False,
    )
