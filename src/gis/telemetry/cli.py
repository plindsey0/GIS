from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.db import session_factory
from gis.models import (
    ConnectionStatus,
    ConnectionType,
    DataSource,
    DataSourceConnection,
    Site,
    Tenant,
)


def configure_connection(
    session: Session, *, tenant_slug: str, site_slug: str, credential_reference: str
) -> DataSourceConnection:
    tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    if tenant is None:
        raise ValueError("tenant not found")
    site = session.scalar(select(Site).where(Site.tenant_id == tenant.id, Site.slug == site_slug))
    if site is None:
        raise ValueError("site not found")
    source = session.scalar(select(DataSource).where(DataSource.key == "first_party"))
    if source is None:
        raise ValueError("first_party source is not seeded")
    connection = session.scalar(
        select(DataSourceConnection).where(
            DataSourceConnection.tenant_id == tenant.id,
            DataSourceConnection.site_id == site.id,
            DataSourceConnection.data_source_id == source.id,
        )
    )
    if connection is None:
        connection = DataSourceConnection(
            tenant_id=tenant.id,
            site_id=site.id,
            data_source_id=source.id,
            connection_type=ConnectionType.CUSTOMER_SIDE,
        )
        session.add(connection)
    connection.credential_reference = credential_reference
    connection.configuration_json = {"transport": "server_to_server", "schema_version": 1}
    connection.status = ConnectionStatus.ACTIVE
    session.commit()
    return connection


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-telemetry", description="Send development telemetry")
    commands = root.add_subparsers(dest="command", required=True)
    configure = commands.add_parser("configure")
    configure.add_argument("--tenant", required=True)
    configure.add_argument("--site", required=True)
    configure.add_argument("--credential-reference", required=True)
    send = commands.add_parser("send")
    send.add_argument("--url", default="http://127.0.0.1:8000")
    send.add_argument("--write-key", required=True)
    send.add_argument("--tenant", default="vahomemath")
    send.add_argument("--site", default="vahomemath")
    send.add_argument("--session-key", type=uuid.UUID, default=uuid.uuid4())
    send.add_argument("--event-id", type=uuid.UUID, default=uuid.uuid4())
    send.add_argument("--event", default="page_view")
    send.add_argument("--page-path", default="/")
    return root


def run(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    if args.command == "configure":
        with session_factory()() as session:
            connection = configure_connection(
                session,
                tenant_slug=args.tenant,
                site_slug=args.site,
                credential_reference=args.credential_reference,
            )
            print(json.dumps({"connection_id": str(connection.id), "status": "ACTIVE"}))
            return 0
    response = requests.post(
        f"{args.url.rstrip('/')}/v1/telemetry/events",
        headers={"X-Telemetry-Key": args.write_key},
        json={
            "tenant_key": args.tenant,
            "site_key": args.site,
            "session_key": str(args.session_key),
            "events": [
                {
                    "event_id": str(args.event_id),
                    "event_name": args.event,
                    "event_version": 1,
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                    "page_path": args.page_path,
                    "properties": {},
                }
            ],
        },
        timeout=30,
    )
    print(json.dumps(response.json()))
    return 0 if response.ok else 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
