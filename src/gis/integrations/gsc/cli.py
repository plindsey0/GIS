from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.db import session_factory
from gis.integrations.gsc.client import GoogleHTTPTransport, GSCClient
from gis.integrations.gsc.config import CollectionGrain, GSCConnectionConfig
from gis.integrations.gsc.credentials import authorized_session
from gis.integrations.gsc.service import GSCCollector, recent_window, validate_connection
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


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        for field in (
            "connection_id",
            "site_id",
            "run_id",
            "property_uri",
            "date",
            "grain",
            "rows",
        ):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(verbose: bool = False) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        handlers=[handler],
        force=True,
    )


def configure_connection(
    session: Session,
    *,
    tenant_slug: str,
    site_slug: str,
    property_uri: str,
    credential_reference: str,
    auth_mode: str,
    grain: CollectionGrain,
    search_type: str,
    optional_dimensions: tuple[str, ...] = (),
    country: str | None = None,
    device: str | None = None,
) -> DataSourceConnection:
    tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    if tenant is None:
        raise ValueError(f"tenant slug not found: {tenant_slug}")
    site = session.scalar(select(Site).where(Site.tenant_id == tenant.id, Site.slug == site_slug))
    if site is None:
        raise ValueError(f"site slug not found in tenant: {site_slug}")
    source = session.scalar(select(DataSource).where(DataSource.key == "google_search_console"))
    if source is None:
        raise ValueError("google_search_console source is not seeded")
    config = GSCConnectionConfig.from_json(
        {
            "property_uri": property_uri,
            "collection_grain": grain.value,
            "search_type": search_type,
            "optional_dimensions": list(optional_dimensions),
            "country": country,
            "device": device,
            "auth_mode": auth_mode,
        }
    )
    connection = session.scalar(
        select(DataSourceConnection).where(
            DataSourceConnection.tenant_id == tenant.id,
            DataSourceConnection.site_id == site.id,
            DataSourceConnection.data_source_id == source.id,
            DataSourceConnection.external_account_id == config.property_uri,
        )
    )
    if connection is None:
        connection = DataSourceConnection(
            tenant_id=tenant.id,
            site_id=site.id,
            data_source_id=source.id,
            external_account_id=config.property_uri,
            connection_type=(
                ConnectionType.BYOD if auth_mode == "oauth" else ConnectionType.NATIVE
            ),
        )
        session.add(connection)
    connection.configuration_json = config.as_json()
    connection.credential_reference = credential_reference
    connection.status = ConnectionStatus.PENDING
    session.commit()
    return connection


def build_client(connection: DataSourceConnection) -> tuple[GSCClient, GSCConnectionConfig]:
    source_config = GSCConnectionConfig.from_json(connection.configuration_json)
    session = authorized_session(source_config.auth_mode, connection.credential_reference)
    return GSCClient(GoogleHTTPTransport(session)), source_config


def command_validate(session: Session, connection_id: uuid.UUID) -> None:
    connection = session.get(DataSourceConnection, connection_id)
    if connection is None:
        raise ValueError("connection not found")
    source = session.get(DataSource, connection.data_source_id)
    if source is None:
        raise ValueError("connection source not found")
    config = validate_connection(connection, source)
    client, _ = build_client(connection)
    client.validate_property(config.property_uri)
    connection.status = ConnectionStatus.ACTIVE
    session.commit()
    print(json.dumps({"connection_id": str(connection.id), "status": "ACTIVE"}))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-gsc", description="Google Search Console collector")
    root.add_argument("--verbose", action="store_true")
    commands = root.add_subparsers(dest="command", required=True)

    configure = commands.add_parser("configure", help="create or update connection metadata")
    configure.add_argument("--tenant", required=True)
    configure.add_argument("--site", required=True)
    configure.add_argument("--property-uri", required=True)
    configure.add_argument("--credential-reference", required=True)
    configure.add_argument(
        "--auth-mode", choices=("service_account", "oauth"), default="service_account"
    )
    configure.add_argument(
        "--grain", choices=[item.value for item in CollectionGrain], default="query-page"
    )
    configure.add_argument("--search-type", default="web")
    configure.add_argument("--optional-dimension", action="append", default=[])
    configure.add_argument("--country")
    configure.add_argument("--device")

    validate = commands.add_parser("validate", help="validate credentials and property access")
    validate.add_argument("--connection", type=uuid.UUID, required=True)

    sync = commands.add_parser("sync", help="collect Search Analytics observations")
    sync.add_argument("--connection", type=uuid.UUID, required=True)
    sync.add_argument("--start-date", type=date.fromisoformat)
    sync.add_argument("--end-date", type=date.fromisoformat)
    sync.add_argument("--recent-days", type=int, default=3)
    sync.add_argument("--grain", choices=[item.value for item in CollectionGrain])
    sync.add_argument("--search-type")
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
                    property_uri=args.property_uri,
                    credential_reference=args.credential_reference,
                    auth_mode=args.auth_mode,
                    grain=CollectionGrain(args.grain),
                    search_type=args.search_type,
                    optional_dimensions=tuple(args.optional_dimension),
                    country=args.country,
                    device=args.device,
                )
                print(json.dumps({"connection_id": str(connection.id), "status": "PENDING"}))
                return 0
            if args.command == "validate":
                command_validate(session, args.connection)
                return 0
            sync_connection = session.get(DataSourceConnection, args.connection)
            if sync_connection is None:
                raise ValueError("connection not found")
            client, _ = build_client(sync_connection)
            if args.start_date or args.end_date:
                if args.start_date is None or args.end_date is None:
                    raise ValueError("--start-date and --end-date must be supplied together")
                start_date, end_date = args.start_date, args.end_date
            else:
                start_date, end_date = recent_window(args.recent_days)
            result = GSCCollector(session, client).sync(
                sync_connection.id,
                start_date,
                end_date,
                grain=CollectionGrain(args.grain) if args.grain else None,
                search_type=args.search_type,
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
        LOGGER.error("gsc_command_failed", extra={"error_type": type(error).__name__})
        print(f"gis-gsc: {error}", file=sys.stderr)
        return 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
