# YAMA Y-276: non-blocking QueueHandler
# YAMA Y-345: secret mask zorunlu
# YAMA Y-348: WARNING count-based rate limit (her N'de 1), trim 200x/sec log flooding YASAK
# YAMA Y-353: stateless (logger factory)

"""
Logging utils - rate limit, correlation, queue.

Y-348: WARNING count-based rate limit every N.
Y-345: secret mask mandatory (delegated to config.secrets).
Y-353: stateless factory, idempotent.
Y-276: non-blocking QueueHandler.
"""

from __future__ import annotations

import logging
import logging.handlers
import uuid
from typing import Final

_WARNING_COUNTERS: dict[str, int] = {}

DEFAULT_LOG_EVERY_N: Final[int] = 100

def new_correlation_id() -> str:
    """Return uuid4 string."""
    return str(uuid.uuid4())

def mask_secrets_in_message(message: str) -> str:
    """
    Mask secrets in message.

    Y-345: delegation to config.secrets.mask_secret.
    Minimal passthrough in FAZ 5a, detailed in 5b.
    """
    try:
        from ..config.secrets import mask_secret

        return mask_secret(message)
    except Exception:
        return message

def log_warning_rate_limited(
    logger: logging.Logger,
    code: str,
    message: str,
    *args,
    every_n: int = DEFAULT_LOG_EVERY_N,
    **kwargs,
) -> None:
    """
    Log warning every N occurrences for given code.

    Y-348: count-based rate limit to prevent trim 200x/sec flooding.
    """
    counter = _WARNING_COUNTERS.get(code, 0) + 1
    _WARNING_COUNTERS[code] = counter

    if counter % every_n == 0:
        logger.warning(message, *args, **kwargs)

def create_logger(name: str) -> logging.Logger:
    """
    Create logger with StreamHandler, idempotent.

    Y-353: stateless factory.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '{"time":"%(asctime)s","name":"%(name)s","level":"%(levelname)s","msg":"%(message)s"}'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    return logger

def create_queue_logger(name: str, queue) -> logging.Logger:
    """
    Create logger with QueueHandler, idempotent.

    Y-276: non-blocking QueueHandler.
    """
    logger = logging.getLogger(name)

    for h in logger.handlers:
        if isinstance(h, logging.handlers.QueueHandler):
            return logger

    qh = logging.handlers.QueueHandler(queue)
    logger.addHandler(qh)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    return logger

def log_info(logger: logging.Logger, message: str, *args, **kwargs) -> None:
    """Info wrapper."""
    logger.info(message, *args, **kwargs)