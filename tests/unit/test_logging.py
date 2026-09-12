# YAMA Y-276: non-blocking QueueHandler
# YAMA Y-345: secret mask
# YAMA Y-348: WARNING rate limit
# YAMA Y-353: stateless factory

"""
Tests for src.utils.logging
"""

import logging
import logging.handlers
import queue
import uuid
from unittest.mock import MagicMock

from src.utils.logging import (
    DEFAULT_LOG_EVERY_N,
    _WARNING_COUNTERS,
    create_logger,
    create_queue_logger,
    log_info,
    log_warning_rate_limited,
    mask_secrets_in_message,
    new_correlation_id,
)

def _clear_counters():
    _WARNING_COUNTERS.clear()

def test_new_correlation_id_is_uuid4():
    cid = new_correlation_id()
    assert isinstance(cid, str)
    assert len(cid) == 36
    assert cid.count("-") == 4
    # valid uuid4
    parsed = uuid.UUID(cid)
    assert str(parsed) == cid

def test_new_correlation_id_unique():
    c1 = new_correlation_id()
    c2 = new_correlation_id()
    assert c1!= c2

def test_log_warning_rate_limited_logs_every_n():
    _clear_counters()
    logger = MagicMock()

    for i in range(1, DEFAULT_LOG_EVERY_N + 1):
        log_warning_rate_limited(logger, "TEST_CODE", "msg %d", i)

    # only at 100th should have called
    assert logger.warning.call_count == 1

def test_log_warning_rate_limited_no_log_before_n():
    _clear_counters()
    logger = MagicMock()

    for i in range(1, DEFAULT_LOG_EVERY_N):
        log_warning_rate_limited(logger, "CODE_99", "msg")

    assert logger.warning.call_count == 0

def test_log_warning_rate_limited_multiple_codes():
    _clear_counters()
    logger = MagicMock()

    for _ in range(100):
        log_warning_rate_limited(logger, "CODE_A", "a")
        log_warning_rate_limited(logger, "CODE_B", "b")

    # each code should have logged once at 100
    assert logger.warning.call_count == 2
    assert _WARNING_COUNTERS["CODE_A"] == 100
    assert _WARNING_COUNTERS["CODE_B"] == 100

def test_log_warning_rate_limited_custom_every_n():
    _clear_counters()
    logger = MagicMock()

    for _ in range(5):
        log_warning_rate_limited(logger, "CUSTOM", "msg", every_n=5)

    assert logger.warning.call_count == 1

    for _ in range(4):
        log_warning_rate_limited(logger, "CUSTOM", "msg", every_n=5)

    # 9 total, no second log
    assert logger.warning.call_count == 1

    log_warning_rate_limited(logger, "CUSTOM", "msg", every_n=5)
    # 10 total -> second log
    assert logger.warning.call_count == 2

def test_create_logger_idempotent():
    name = "test.idempotent.logger"
    # clean existing
    existing = logging.getLogger(name)
    existing.handlers.clear()

    l1 = create_logger(name)
    count1 = len(l1.handlers)

    l2 = create_logger(name)
    count2 = len(l2.handlers)

    assert l1 is l2
    assert count1 == count2 == 1

    # cleanup
    l1.handlers.clear()

def test_create_queue_logger_attaches_handler():
    name = "test.queue.logger"
    existing = logging.getLogger(name)
    existing.handlers.clear()

    q = queue.Queue()
    logger = create_queue_logger(name, q)

    has_qh = any(isinstance(h, logging.handlers.QueueHandler) for h in logger.handlers)
    assert has_qh

    # idempotent second call should not add second QueueHandler
    logger2 = create_queue_logger(name, q)
    qh_count = sum(1 for h in logger2.handlers if isinstance(h, logging.handlers.QueueHandler))
    assert qh_count == 1

    # cleanup
    logger.handlers.clear()

def test_mask_secrets_in_message_passthrough():
    msg = "this message has no secrets"
    result = mask_secrets_in_message(msg)
    assert result == msg

def test_log_info_calls_logger_info():
    logger = MagicMock()
    log_info(logger, "hello %s", "world")
    logger.info.assert_called_once_with("hello %s", "world")

def test_warning_counters_dict_exists():
    assert isinstance(_WARNING_COUNTERS, dict)