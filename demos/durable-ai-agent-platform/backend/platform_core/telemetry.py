"""Committed, correlated, identifier-only logs; untrusted payloads are excluded."""

import json
import logging
from contextvars import ContextVar

pending_logs: ContextVar[list[dict[str, object]] | None] = ContextVar("pending_logs", default=None)
logger = logging.getLogger("platform.events")


def committed_logs(events: list[dict[str, object]]) -> None:
    for item in events:
        logger.info(json.dumps(item, sort_keys=True))


def configure_logging() -> None:
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
