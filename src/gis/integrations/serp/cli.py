from __future__ import annotations

import argparse
import json
import os
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.db import session_factory
from gis.integrations.serp.dataforseo import DataForSEOProvider
from gis.integrations.serp.service import SerpCollector, estimate_cost, normalize_query
from gis.models import (
    ConnectionStatus,
    ConnectionType,
    DataSource,
    DataSourceConnection,
    SerpObservation,
    Site,
    Tenant,
    TrackedQuery,
)


def _scope(session: Session, tenant_slug: str, site_slug: str) -> tuple[Tenant, Site]:
    tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    if tenant is None:
        raise ValueError("tenant not found")
    site = session.scalar(select(Site).where(Site.tenant_id == tenant.id, Site.slug == site_slug))
    if site is None:
        raise ValueError("site not found")
    return tenant, site


def configure_connection(
    session: Session, tenant_slug: str, site_slug: str, credential_reference: str
) -> DataSourceConnection:
    tenant, site = _scope(session, tenant_slug, site_slug)
    source = session.scalar(select(DataSource).where(DataSource.key == "dataforseo"))
    if source is None:
        raise ValueError("dataforseo source is not seeded")
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
            connection_type=ConnectionType.LICENSED_ENRICHMENT,
        )
        session.add(connection)
    connection.credential_reference = credential_reference
    connection.status = ConnectionStatus.PENDING
    connection.configuration_json = {
        "provider": "dataforseo",
        "endpoint": "google_organic_live_advanced",
    }
    session.commit()
    return connection


def add_query(
    session: Session, tenant_slug: str, site_slug: str, query_text: str, **context: object
) -> TrackedQuery:
    tenant, site = _scope(session, tenant_slug, site_slug)
    values = {
        "device": "desktop",
        "country_code": "US",
        "language_code": "en",
        "requested_depth": 100,
        "cadence": "WEEKLY",
        **context,
    }
    normalized = normalize_query(query_text)
    query = session.scalar(
        select(TrackedQuery).where(
            TrackedQuery.tenant_id == tenant.id,
            TrackedQuery.site_id == site.id,
            TrackedQuery.normalized_query == normalized,
            TrackedQuery.device == values["device"],
            TrackedQuery.country_code == values["country_code"],
            TrackedQuery.language_code == values["language_code"],
            TrackedQuery.location_code == values.get("location_code"),
        )
    )
    if query is None:
        query = TrackedQuery(
            tenant_id=tenant.id,
            site_id=site.id,
            query_text=query_text.strip(),
            normalized_query=normalized,
            **values,
        )
        session.add(query)
    else:
        query.active = True
    session.commit()
    return query


def _credentials(reference: str | None) -> tuple[str, str]:
    if not reference or not reference.startswith("env:"):
        raise ValueError("DataForSEO credential reference must use env:VARIABLE")
    raw = os.environ.get(reference[4:])
    if not raw:
        raise ValueError("referenced credential is unavailable")
    payload = json.loads(raw)
    return str(payload["login"]), str(payload["password"])


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-serp")
    commands = root.add_subparsers(dest="command", required=True)
    configure = commands.add_parser("configure")
    configure.add_argument("--tenant", required=True)
    configure.add_argument("--site", required=True)
    configure.add_argument("--credential-reference", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--connection", type=uuid.UUID, required=True)
    add = commands.add_parser("add")
    add.add_argument("--tenant", required=True)
    add.add_argument("--site", required=True)
    add.add_argument("--query", action="append", required=True)
    add.add_argument("--device", default="desktop")
    add.add_argument("--country", default="US")
    add.add_argument("--language", default="en")
    add.add_argument("--location-code", type=int)
    add.add_argument("--depth", type=int, default=100)
    add.add_argument("--cadence", choices=("ONCE", "DAILY", "WEEKLY"), default="WEEKLY")
    listing = commands.add_parser("list")
    listing.add_argument("--tenant", required=True)
    listing.add_argument("--site", required=True)
    disable = commands.add_parser("disable")
    disable.add_argument("--query-id", type=uuid.UUID, required=True)
    estimate = commands.add_parser("estimate")
    estimate.add_argument("--queries", type=int, required=True)
    estimate.add_argument("--cadence", choices=("ONCE", "DAILY", "WEEKLY"), required=True)
    estimate.add_argument("--unit-cost", type=Decimal, default=Decimal("0.002"))
    sync = commands.add_parser("sync")
    sync.add_argument("--connection", type=uuid.UUID, required=True)
    sync.add_argument("--query-id", type=uuid.UUID, required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--limit", type=int, default=20)
    return root


def run(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    output: object
    try:
        with session_factory()() as session:
            if args.command == "configure":
                output = {
                    "connection_id": str(
                        configure_connection(
                            session, args.tenant, args.site, args.credential_reference
                        ).id
                    )
                }
            elif args.command == "validate":
                connection = session.get(DataSourceConnection, args.connection)
                if connection is None:
                    raise ValueError("connection not found")
                _credentials(connection.credential_reference)
                output = {"connection_id": str(connection.id), "status": "CREDENTIAL_AVAILABLE"}
            elif args.command == "add":
                output = {
                    "query_ids": [
                        str(
                            add_query(
                                session,
                                args.tenant,
                                args.site,
                                text,
                                device=args.device,
                                country_code=args.country,
                                language_code=args.language,
                                location_code=args.location_code,
                                requested_depth=args.depth,
                                cadence=args.cadence,
                            ).id
                        )
                        for text in args.query
                    ]
                }
            elif args.command == "list":
                tenant, site = _scope(session, args.tenant, args.site)
                query_rows = session.scalars(
                    select(TrackedQuery)
                    .where(TrackedQuery.tenant_id == tenant.id, TrackedQuery.site_id == site.id)
                    .order_by(TrackedQuery.normalized_query)
                ).all()
                output = [
                    {
                        "id": str(row.id),
                        "query": row.query_text,
                        "active": row.active,
                        "cadence": row.cadence,
                    }
                    for row in query_rows
                ]
            elif args.command == "disable":
                row = session.get(TrackedQuery, args.query_id)
                if row is None:
                    raise ValueError("tracked query not found")
                row.active = False
                session.commit()
                output = {"query_id": str(row.id), "active": False}
            elif args.command == "estimate":
                output = estimate_cost(args.queries, args.cadence, args.unit_cost).to_dict()
            elif args.command == "sync":
                connection = session.get(DataSourceConnection, args.connection)
                query = session.get(TrackedQuery, args.query_id)
                if connection is None or query is None:
                    raise ValueError("connection or tracked query not found")
                login, password = _credentials(connection.credential_reference)
                run = SerpCollector(session, DataForSEOProvider(login, password)).sync(
                    connection.id, query
                )
                output = {"run_id": str(run.id), "status": run.status.value}
            else:
                observation_rows = session.scalars(
                    select(SerpObservation)
                    .order_by(SerpObservation.observed_at.desc())
                    .limit(args.limit)
                ).all()
                output = [
                    {
                        "id": str(row.id),
                        "query": row.query_text,
                        "observed_at": row.observed_at.isoformat(),
                    }
                    for row in observation_rows
                ]
        print(json.dumps(output))
        return 0
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error)}))
        return 2


def main() -> None:
    raise SystemExit(run())
