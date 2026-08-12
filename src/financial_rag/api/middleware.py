"""Request correlation and privacy-conscious HTTP logging."""

import re
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}")
RequestHandler = Callable[[Request], Awaitable[Response]]


def safe_route_path(request: Request) -> str:
    """Return the declared route template, never an arbitrary raw request path."""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else "<unmatched>"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a bounded request ID and log no body, query string, or credentials."""

    async def dispatch(self, request: Request, call_next: RequestHandler) -> Response:
        supplied = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = supplied if _REQUEST_ID_PATTERN.fullmatch(supplied) else uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "api_request_completed",
            request_id=request_id,
            method=request.method,
            path=safe_route_path(request),
            status_code=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return response
