"""One error format for the whole API: RFC 7807 problem+json with a stable `code` and a `traceId`.

Same idea as backend_web's ProblemDetail + GlobalExceptionHandler. Services raise `ApiError`;
the handlers below turn every error (ours, FastAPI's, or unexpected) into the same shape.
"""
import logging
import uuid
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)

PROBLEM_JSON = "application/problem+json"


class ApiError(Exception):
    """Raise from a service to send a problem+json response."""

    def __init__(self, status: int, code: str, detail: str, **extra):
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.extra = extra


def problem_response(status: int, code: str, detail: str, trace_id: str | None = None, **extra) -> JSONResponse:
    body = {
        "type": "about:blank",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "code": code,
        "traceId": trace_id or uuid.uuid4().hex,
        **extra,
    }
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


_CODES_BY_STATUS = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 400: "BAD_REQUEST", 409: "CONFLICT"}


def install_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return problem_response(exc.status, exc.code, exc.detail, **exc.extra)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        code = _CODES_BY_STATUS.get(exc.status_code, "HTTP_ERROR")
        return problem_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        errors = [
            {"field": ".".join(str(p) for p in e["loc"][1:]) or str(e["loc"][0]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return problem_response(400, "VALIDATION_FAILED", "The request is not valid.", errors=errors)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception):
        trace_id = uuid.uuid4().hex
        log.error("Unhandled error (traceId=%s)", trace_id, exc_info=exc)
        return problem_response(500, "INTERNAL_ERROR", "Something went wrong on the server.", trace_id=trace_id)
