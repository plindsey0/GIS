from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from gis.api.errors import ApiError
from gis.api.errors import response as error_response
from gis.api.routes import router as workbench_router
from gis.db import session_factory
from gis.integrations.gsc.credentials import CredentialResolutionError
from gis.telemetry.schemas import TelemetryBatchInput, TelemetryResponse
from gis.telemetry.security import authorize
from gis.telemetry.service import TelemetryService, resolve_context

LOGGER = logging.getLogger(__name__)
DEFAULT_MAX_PAYLOAD_BYTES = 65_536


def max_payload_bytes() -> int:
    return int(os.environ.get("TELEMETRY_MAX_PAYLOAD_BYTES", DEFAULT_MAX_PAYLOAD_BYTES))


def create_app() -> FastAPI:
    app = FastAPI(
        title="GIS Application API",
        version="1.0",
        description="Versioned operational API over governed GIS domain services.",
    )
    origins = [
        item.strip()
        for item in os.environ.get("GIS_API_CORS_ORIGINS", "http://localhost:3000").split(",")
        if item.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT"],
        allow_headers=["Content-Type", "X-GIS-Operator-Key", "X-GIS-Role"],
    )

    @app.exception_handler(ApiError)
    async def api_error(request: Request, error: ApiError) -> JSONResponse:
        return error_response(request, error)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        if request.url.path.startswith("/api/v1"):
            return error_response(
                request,
                ApiError(
                    422, "REQUEST_INVALID", "Request validation failed.", details=error.errors()
                ),
            )
        return JSONResponse(status_code=422, content={"detail": error.errors()})

    @app.middleware("http")
    async def limit_payload(request: Request, call_next: object) -> object:
        request.state.request_id = uuid.uuid4()
        started = time.monotonic()
        if request.url.path == "/v1/telemetry/events":
            length = request.headers.get("content-length")
            if length is not None and int(length) > max_payload_bytes():
                return JSONResponse(status_code=413, content={"detail": "payload too large"})
            body = await request.body()
            if len(body) > max_payload_bytes():
                return JSONResponse(status_code=413, content={"detail": "payload too large"})
        response = await call_next(request)  # type: ignore[operator]
        response.headers["X-Request-ID"] = str(request.state.request_id)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/v1"):
            LOGGER.info(
                "application_request_complete",
                extra={
                    "request_id": str(request.state.request_id),
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "processing_ms": round((time.monotonic() - started) * 1000, 2),
                },
            )
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/telemetry/events", response_model=TelemetryResponse)
    def ingest(
        payload: TelemetryBatchInput,
        x_telemetry_key: Optional[str] = Header(default=None),
    ) -> TelemetryResponse:
        if not x_telemetry_key:
            raise HTTPException(status_code=401, detail="telemetry authorization required")
        request_id = uuid.uuid4()
        started = time.monotonic()
        with session_factory()() as session:
            try:
                context = resolve_context(session, payload.tenant_key, payload.site_key)
                authorize(context.connection.credential_reference, x_telemetry_key)
            except PermissionError as error:
                raise HTTPException(
                    status_code=403, detail="telemetry authorization failed"
                ) from error
            except CredentialResolutionError as error:
                raise HTTPException(
                    status_code=503, detail="telemetry authorization unavailable"
                ) from error
            except LookupError as error:
                raise HTTPException(status_code=404, detail=str(error)) from error
            result = TelemetryService(session).ingest(payload, context, request_id=request_id)
            LOGGER.info(
                "telemetry_request_complete",
                extra={
                    "request_id": str(request_id),
                    "tenant_id": str(context.tenant.id),
                    "site_id": str(context.site.id),
                    "accepted": result.accepted,
                    "duplicates": result.duplicates,
                    "rejected": result.rejected,
                    "processing_ms": round((time.monotonic() - started) * 1000, 2),
                },
            )
            return result

    app.include_router(workbench_router)

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "gis.api.app:app",
        host="127.0.0.1",
        port=int(os.environ.get("GIS_API_PORT", "8000")),
        reload=False,
    )
