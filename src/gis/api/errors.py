from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self, status: int, code: str, message: str, *, details: Any = None, retryable: bool = False
    ) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        self.retryable = retryable


def response(request: Request, error: ApiError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", uuid.uuid4())
    return JSONResponse(
        status_code=error.status,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "request_id": str(request_id),
                "details": error.details,
                "retryable": error.retryable,
            }
        },
    )
