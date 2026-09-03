from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.db import session_factory
from gis.integrations.ga4.client import GA4Client, GoogleGA4Transport
from gis.integrations.ga4.config import ALL_DATASETS, GA4ConnectionConfig, GA4Dataset
from gis.integrations.ga4.service import GA4Collector, validate_connection
from gis.integrations.gsc.cli import configure_logging
from gis.integrations.gsc.credentials import authorized_session
from gis.models import (
    ConnectionStatus,
    ConnectionType,
    DataSource,
    DataSourceConnection,
    IngestionStatus,
    Site,
    Tenant,
)

LOGGER = logging.getLogger(__name__)
ANALYTICS_READONLY_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


def configure_connection(
    session: Session,
    *,
    tenant_slug: str,
    site_slug: str,
    property_id: str,
    credential_reference: str,
    auth_mode: str,
    property_timezone: str | None = None,
) -> DataSourceConnection:
    tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    if tenant is None:
        raise ValueError(f"tenant slug not found: {tenant_slug}")
    site = session.scalar(select(Site).where(Site.tenant_id == tenant.id, Site.slug == site_slug))
    if site is None:
        raise ValueError(f"site slug not found in tenant: {site_slug}")
    source = session.scalar(select(DataSource).where(DataSource.key == "ga4"))
    if source is None:
        raise ValueError("ga4 source is not seeded")
    config = GA4ConnectionConfig.from_json(
        {
            "property_id": property_id,
            "auth_mode": auth_mode,
            "property_timezone": property_timezone,
            "default_datasets": [dataset.value for dataset in ALL_DATASETS],
        }
    )
    connection = session.scalar(
        select(DataSourceConnection).where(
            DataSourceConnection.tenant_id == tenant.id,
            DataSourceConnection.site_id == site.id,
            DataSourceConnection.data_source_id == source.id,
            DataSourceConnection.external_account_id == config.property_id,
        )
    )
    if connection is None:
        connection = DataSourceConnection(
            tenant_id=tenant.id,
            site_id=site.id,
            data_source_id=source.id,
            external_account_id=config.property_id,
        )
        session.add(connection)
    connection.configuration_json = config.as_json()
    connection.credential_reference = credential_reference
    connection.connection_type = (
        ConnectionType.BYOD if auth_mode == "oauth" else ConnectionType.NATIVE
    )
    connection.status = ConnectionStatus.PENDING
    session.commit()
    return connection


def build_client(connection: DataSourceConnection) -> tuple[GA4Client, GA4ConnectionConfig]:
    config = GA4ConnectionConfig.from_json(connection.configuration_json)
    auth_session = authorized_session(
        config.auth_mode,
        connection.credential_reference,
        scopes=[ANALYTICS_READONLY_SCOPE],
    )
    return GA4Client(GoogleGA4Transport(auth_session)), config


def command_validate(session: Session, connection_id: uuid.UUID) -> None:
    connection = session.get(DataSourceConnection, connection_id)
    if connection is None:
        raise ValueError("connection not found")
    source = session.get(DataSource, connection.data_source_id)
    if source is None:
        raise ValueError("connection source not found")
    config = validate_connection(connection, source)
    client, _ = build_client(connection)
    property_timezone = client.validate_property(config.property_resource)
    if config.property_timezone and config.property_timezone != property_timezone:
        raise ValueError("configured property timezone does not match GA4 metadata")
    connection.status = ConnectionStatus.ACTIVE
    session.commit()
    print(
        json.dumps(
            {
                "connection_id": str(connection.id),
                "status": "ACTIVE",
                "property_timezone": property_timezone,
            }
        )
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-ga4", description="GA4 aggregate collector")
    root.add_argument("--verbose", action="store_true")
    commands = root.add_subparsers(dest="command", required=True)

    configure = commands.add_parser("configure", help="create or update connection metadata")
    configure.add_argument("--tenant", required=True)
    configure.add_argument("--site", required=True)
    configure.add_argument("--property-id", required=True)
    configure.add_argument("--credential-reference", required=True)
    configure.add_argument(
        "--auth-mode", choices=("service_account", "oauth"), default="service_account"
    )
    configure.add_argument("--property-timezone")

    validate = commands.add_parser("validate", help="validate credentials and property access")
    validate.add_argument("--connection", type=uuid.UUID, required=True)

    sync = commands.add_parser("sync", help="collect aggregate GA4 reports")
    sync.add_argument("--connection", type=uuid.UUID, required=True)
    sync.add_argument("--start-date", type=date.fromisoformat)
    sync.add_argument("--end-date", type=date.fromisoformat)
    sync.add_argument("--recent-days", type=int, default=3)
    sync.add_argument(
        "--dataset",
        action="append",
        choices=("all", *[dataset.value for dataset in ALL_DATASETS]),
        default=[],
    )
    sync.add_argument("--dry-run", action="store_true")
    return root


def run(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    configure_logging(args.verbose)
    try:
        with session_factory()() as session:
            if args.command == "configure":
                connection = configure_connection(
                    session,
                    tenant_slug=args.tenant,
                    site_slug=args.site,
                    property_id=args.property_id,
                    credential_reference=args.credential_reference,
                    auth_mode=args.auth_mode,
                    property_timezone=args.property_timezone,
                )
                print(json.dumps({"connection_id": str(connection.id), "status": "PENDING"}))
                return 0
            if args.command == "validate":
                command_validate(session, args.connection)
                return 0
            sync_connection = session.get(DataSourceConnection, args.connection)
            if sync_connection is None:
                raise ValueError("connection not found")
            from gis.provider_control.binding import guard_free_collection

            guard_free_collection(session, sync_connection, "ga4", str(sync_connection.site_id))
            if (args.start_date is None) != (args.end_date is None):
                raise ValueError("--start-date and --end-date must be supplied together")
            selected = tuple(ALL_DATASETS)
            if args.dataset and "all" not in args.dataset:
                selected = tuple(GA4Dataset(value) for value in dict.fromkeys(args.dataset))
            client, _ = build_client(sync_connection)
            result = GA4Collector(session, client).sync(
                sync_connection.id,
                args.start_date,
                args.end_date,
                recent_days=args.recent_days,
                datasets=selected,
                dry_run=args.dry_run,
            )
            print(
                json.dumps(
                    {
                        "run_id": str(result.id),
                        "status": result.status.value,
                        "records_received": result.records_received,
                        "records_inserted": result.records_inserted,
                        "records_rejected": result.records_rejected,
                    }
                )
            )
            return 0 if result.status is IngestionStatus.SUCCEEDED else 1
    except Exception as error:
        LOGGER.error("ga4_command_failed", extra={"error_type": type(error).__name__})
        print(f"gis-ga4: {error}", file=sys.stderr)
        return 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
