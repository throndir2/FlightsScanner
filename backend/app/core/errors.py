"""Consistent API error envelope: ``{ "detail": ..., "code": ... }``.

Register :func:`api_error_handler` on the FastAPI app so routes can raise :class:`APIError`
with a machine-readable ``code`` (see ``docs/api-spec.md``).
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class APIError(Exception):
    """An application error carrying an HTTP status and a machine-readable code."""

    def __init__(self, status_code: int, detail: str, code: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code


async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )
