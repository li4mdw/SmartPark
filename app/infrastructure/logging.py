import json
import logging
import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from collections.abc import Iterator
from typing import Any


_STANDARD_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__)
_request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_uuid_context: ContextVar[str | None] = ContextVar("user_uuid", default=None)
_CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class RequestContextFilter(logging.Filter):
    """Attach request correlation fields to every log produced in a request."""

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = _request_id_context.get()
        user_uuid = _user_uuid_context.get()
        if request_id is not None and not hasattr(record, "request_id"):
            record.request_id = request_id
        if user_uuid is not None and not hasattr(record, "user_uuid"):
            record.user_uuid = user_uuid
        return True


@contextmanager
def request_log_context(
    request_id: str,
    user_uuid: str | None = None,
) -> Iterator[None]:
    request_token = _request_id_context.set(request_id)
    user_token = _user_uuid_context.set(user_uuid)
    try:
        yield
    finally:
        _user_uuid_context.reset(user_token)
        _request_id_context.reset(request_token)


def outbound_trace_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    request_id = _request_id_context.get()
    user_uuid = _user_uuid_context.get()
    if request_id is not None:
        headers["x-request-id"] = request_id
    if user_uuid is not None:
        headers["x-user-uuid"] = user_uuid
    return headers


def valid_correlation_id(value: str | None) -> str | None:
    if value is None or _CORRELATION_ID_PATTERN.fullmatch(value) is None:
        return None
    return value


class JsonFormatter(logging.Formatter):
    """Render application logs as one JSON object per line."""

    def __init__(self, service_name: str = "smartpark-api") -> None:
        super().__init__()
        self._service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "severity": record.levelname,
            "service": self._service_name,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_FIELDS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestContextFilter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
