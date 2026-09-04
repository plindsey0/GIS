"""Explicit non-billable WhoAmI control-plane refresh; no collector, scheduler or usage entries."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import DataSource, DataSourceConnection, ProviderAccountTelemetry
from gis.provider_control.credentials import builtwith_credentials

ENDPOINT = "https://api.builtwith.com/whoamiv1/api.json"
FRESHNESS = timedelta(hours=24)


class TelemetryFailure(ValueError):
    pass


def normalize(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("Errors") or payload.get("error"):
        raise TelemetryFailure("PROVIDER_ERROR")
    credits, limits, privacy = (payload.get(key) for key in ("credits", "rate_limits", "privacy"))
    if (
        not isinstance(credits, dict)
        or not isinstance(limits, dict)
        or not isinstance(privacy, dict)
    ):
        raise TelemetryFailure("MALFORMED_RESPONSE")

    def number(value: Any) -> str | None:
        if value is None:
            return None
        try:
            if isinstance(value, bool):
                raise ValueError
            parsed = Decimal(str(value))
            if not parsed.is_finite() or parsed < 0 or parsed > Decimal("1e30"):
                raise ValueError
            return str(parsed)
        except (ValueError, InvalidOperation):
            raise TelemetryFailure("MALFORMED_RESPONSE") from None

    result: dict[str, Any] = {
        "credits_remaining": number(credits.get("remaining")),
        "credits_purchased": number(credits.get("purchased")),
        "credits_used": number(credits.get("used")),
        "requests_per_second": number(limits.get("requests_per_second")),
        "concurrency": number(limits.get("concurrency")),
    }
    if result["credits_remaining"] is None:
        raise TelemetryFailure("MALFORMED_RESPONSE")
    result["pii_allowed"] = (
        privacy.get("pii_allowed") if isinstance(privacy.get("pii_allowed"), bool) else None
    )
    result["privacy_mode"] = (
        privacy.get("default_privacy_mode")
        if privacy.get("default_privacy_mode") in {"pii", "nopii"}
        else None
    )
    flags = privacy.get("flags_supported")
    result["privacy_flags"] = [
        flag for flag in ("NOPII", "NOMETA", "NOATTR") if isinstance(flags, list) and flag in flags
    ]
    endpoints = payload.get("endpoints")
    operations = endpoints.get("operations") if isinstance(endpoints, dict) else None
    # Endpoint inventory means advertised API availability, not licensed entitlement.
    result["domain_api_advertised"] = (
        any(
            isinstance(item, dict)
            and item.get("id") == "domain.lookup"
            and item.get("path") == "/v23/api.json"
            for item in operations
        )
        if isinstance(operations, list)
        else None
    )
    return result


class WhoAmIProvider:
    def __init__(self, key: str, http: Any = None):
        self.key, self.http = key, http or requests.Session()

    def retrieve(self) -> dict[str, Any]:
        try:
            response = self.http.get(
                ENDPOINT,
                headers={"Authorization": f"API {self.key}"},
                timeout=(3, 5),
                allow_redirects=False,
            )
            if response.status_code != 200:
                raise TelemetryFailure(
                    {
                        401: "AUTHENTICATION_FAILED",
                        403: "AUTHORIZATION_FAILED",
                        429: "RATE_LIMITED",
                    }.get(response.status_code, "PROVIDER_ERROR")
                )
            import json

            return normalize(json.loads(response.text, parse_float=str))
        except TelemetryFailure:
            raise
        except requests.Timeout:
            raise TelemetryFailure("TIMEOUT") from None
        except requests.RequestException:
            raise TelemetryFailure("TRANSPORT_ERROR") from None
        except (ValueError, TypeError):
            raise TelemetryFailure("MALFORMED_RESPONSE") from None


def latest(session: Session, connection: DataSourceConnection) -> ProviderAccountTelemetry | None:
    return session.scalar(
        select(ProviderAccountTelemetry)
        .where(
            ProviderAccountTelemetry.connection_id == connection.id,
            ProviderAccountTelemetry.tenant_id == connection.tenant_id,
        )
        .order_by(ProviderAccountTelemetry.checked_at.desc(), ProviderAccountTelemetry.id.desc())
        .limit(1)
    )


def telemetry_status(
    session: Session, connection: DataSourceConnection, now: datetime | None = None
) -> dict[str, Any]:
    row = latest(session, connection)
    now = now or datetime.now(timezone.utc)
    return {
        "state": (
            "STALE" if row.status == "CURRENT" and now - row.checked_at > FRESHNESS else row.status
        )
        if row
        else "UNKNOWN",
        "checked_at": row.checked_at.isoformat() if row else None,
        "values": row.normalized if row else {},
        "failure_category": row.failure_category if row else None,
        "credit_cost": "0",
        "cost_basis": "Official WhoAmI documentation; no purchased API credits",
        "freshness_hours": 24,
        "automatic_refresh": False,
        "execution_held": os.environ.get("GIS_PAID_EXECUTION_DISABLED") == "1",
    }


def refresh(
    session: Session,
    connection: DataSourceConnection,
    actor: str,
    provider: WhoAmIProvider | None = None,
) -> ProviderAccountTelemetry:
    source = session.get(DataSource, connection.data_source_id)
    if not source or source.key != "builtwith":
        raise ValueError("Account telemetry is implemented only for BuiltWith")
    # Conservative: keep the existing process hold effective even for credit-free refreshes.
    if os.environ.get("GIS_PAID_EXECUTION_DISABLED") == "1":
        raise ValueError("Execution hold is enabled; no account request was made")
    now = datetime.now(timezone.utc)
    previous = latest(session, connection)
    if previous and now - previous.checked_at < timedelta(minutes=1):
        raise ValueError("Wait one minute between explicit account refreshes")
    row = ProviderAccountTelemetry(
        tenant_id=connection.tenant_id,
        connection_id=connection.id,
        checked_at=now,
        actor=actor,
        status="UNAVAILABLE",
        normalized={},
    )
    try:
        selected = provider or WhoAmIProvider(
            builtwith_credentials(connection.credential_reference)
        )
        row.normalized = selected.retrieve()
        row.status = "CURRENT"
    except TelemetryFailure as error:
        row.failure_category = str(error)
    except Exception:
        row.failure_category = "CREDENTIAL_OR_INTERNAL_ERROR"
    session.add(row)
    session.flush()
    return row
