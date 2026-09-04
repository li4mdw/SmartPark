import json
import logging

from app.infrastructure.logging import JsonFormatter, RequestContextFilter, request_log_context


def test_json_logging_includes_request_context() -> None:
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="test_event",
        args=(),
        exc_info=None,
    )

    with request_log_context("request-123", "user-456"):
        RequestContextFilter().filter(record)
        payload = json.loads(JsonFormatter().format(record))

    assert payload["request_id"] == "request-123"
    assert payload["user_uuid"] == "user-456"
    assert payload["message"] == "test_event"


def test_json_logging_does_not_add_empty_request_context() -> None:
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="startup_event",
        args=(),
        exc_info=None,
    )

    RequestContextFilter().filter(record)
    payload = json.loads(JsonFormatter().format(record))

    assert "request_id" not in payload
    assert "user_uuid" not in payload
