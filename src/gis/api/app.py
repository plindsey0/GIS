from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

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
    app = FastAPI(title="VAHomeMath GIS Telemetry API", version="1.0")

    @app.middleware("http")
    async def limit_payload(request: Request, call_next: object) -> object:
        if request.url.path == "/v1/telemetry/events":
            length = request.headers.get("content-length")
            if length is not None and int(length) > max_payload_bytes():
                return JSONResponse(status_code=413, content={"detail": "payload too large"})
            body = await request.body()
            if len(body) > max_payload_bytes():
                return JSONResponse(status_code=413, content={"detail": "payload too large"})
        return await call_next(request)  # type: ignore[operator]

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

    return app


app = create_app()
