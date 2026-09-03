"""Execution-worker attestations and operator health, without secrets or provider I/O."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    DataSource,
    DataSourceConnection,
    ExecutorHeartbeat,
    ExecutorRole,
    ProviderCollectionPolicy,
)
from gis.provider_control.credentials import probe


def attest(session: Session) -> dict[str, Any]:
    rows = session.scalars(
        select(DataSourceConnection).join(DataSource).where(DataSource.key == "dataforseo")
    ).all()
    return {
        "provider_credentials": {str(c.id): probe(c.credential_reference) for c in rows},
        "paid_execution_disabled": os.environ.get("GIS_PAID_EXECUTION_DISABLED") == "1",
    }


def readiness(session: Session, connection: DataSourceConnection | None) -> dict[str, Any]:
    if connection is None:
        return {
            "state": "NOT_CONNECTED",
            "runnable": False,
            "worker_verified": False,
            "reason": "No connection selected",
        }
    local = probe(connection.credential_reference)
    workers = session.scalars(
        select(ExecutorHeartbeat).where(
            ExecutorHeartbeat.role == ExecutorRole.WORKER,
            ExecutorHeartbeat.lease_expires_at > datetime.now(timezone.utc),
        )
    ).all()
    checks = [
        w.metadata_json.get("provider_credentials", {}).get(str(connection.id)) for w in workers
    ]
    verified = bool(checks) and all(
        c
        and c.get("reference_fingerprint") == local["reference_fingerprint"]
        and c.get("state") == "CONNECTED_AND_RESOLVABLE"
        for c in checks
    )
    disabled = any(w.metadata_json.get("paid_execution_disabled") for w in workers)
    state = (
        "CONNECTED_AND_RESOLVABLE"
        if verified
        else "INVALID_CONFIGURATION"
        if local["state"] == "INVALID_CONFIGURATION"
        else "CONNECTED_CREDENTIAL_UNAVAILABLE"
    )
    return {
        "state": state,
        "runnable": verified and not disabled and connection.status.value == "ACTIVE",
        "worker_verified": verified,
        "api_resolution": local["state"],
        "authentication": "NOT_EXTERNALLY_VALIDATED",
        "execution_held": disabled,
        "reason": "Paid execution is held for no-call validation"
        if disabled
        else "Credential resolved by live execution worker; provider authentication is not yet validated"
        if verified
        else "The configured credential is unavailable or not yet verified by a live execution worker",
    }


def main() -> None:
    from gis.db import session_factory

    with session_factory()() as session:
        connections = session.scalars(
            select(DataSourceConnection)
            .join(DataSource)
            .join(
                ProviderCollectionPolicy,
                ProviderCollectionPolicy.data_source_connection_id == DataSourceConnection.id,
            )
            .where(
                DataSource.key == "dataforseo",
                ProviderCollectionPolicy.master_enabled.is_(True),
                ProviderCollectionPolicy.status == "ACTIVE",
            )
        ).all()
        for connection in connections:
            if probe(connection.credential_reference)["state"] != "CONNECTED_AND_RESOLVABLE":
                print(
                    "WARNING: DataForSEO collection policy is ACTIVE but credential is unavailable to the worker runtime; collection will fail closed."
                )


if __name__ == "__main__":
    main()
