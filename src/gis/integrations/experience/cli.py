from __future__ import annotations

import argparse
import json
import os
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.db import session_factory
from gis.integrations.experience.pagespeed import PageSpeedProvider
from gis.integrations.experience.service import ExperienceCollector
from gis.models import (
    ConnectionStatus,
    ConnectionType,
    DataSource,
    DataSourceConnection,
    ExperienceObservation,
    ExperienceScope,
    FormFactor,
    Site,
    Tenant,
)


def configure_connection(
    session: Session, tenant_slug: str, site_slug: str, credential_reference: str | None
) -> DataSourceConnection:
    tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    site = (
        session.scalar(select(Site).where(Site.tenant_id == tenant.id, Site.slug == site_slug))
        if tenant
        else None
    )
    source = session.scalar(select(DataSource).where(DataSource.key == "pagespeed"))
    if tenant is None or site is None or source is None:
        raise ValueError("tenant, site, or pagespeed source not found")
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
            connection_type=ConnectionType.NATIVE,
        )
        session.add(connection)
    connection.credential_reference = credential_reference
    connection.configuration_json = {"provider": "pagespeed"}
    connection.status = ConnectionStatus.PENDING
    session.commit()
    return connection


def _key(reference: str | None) -> str | None:
    if reference is None:
        return None
    if not reference.startswith("env:"):
        raise ValueError("PageSpeed credential reference must use env:VARIABLE")
    value = os.environ.get(reference[4:])
    if not value:
        raise ValueError("referenced credential is unavailable")
    return value


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-experience")
    commands = root.add_subparsers(dest="command", required=True)
    configure = commands.add_parser("configure")
    configure.add_argument("--tenant", required=True)
    configure.add_argument("--site", required=True)
    configure.add_argument("--credential-reference")
    validate = commands.add_parser("validate")
    validate.add_argument("--connection", type=uuid.UUID, required=True)
    sync = commands.add_parser("sync")
    sync.add_argument("--connection", type=uuid.UUID, required=True)
    sync.add_argument("--target", required=True)
    sync.add_argument("--form-factor", choices=("MOBILE", "DESKTOP"), default="MOBILE")
    sync.add_argument("--scope", choices=("URL", "ORIGIN"), default="URL")
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
                _key(connection.credential_reference)
                output = {"connection_id": str(connection.id), "status": "CONFIGURATION_VALID"}
            elif args.command == "sync":
                connection = session.get(DataSourceConnection, args.connection)
                if connection is None:
                    raise ValueError("connection not found")
                run = ExperienceCollector(
                    session, PageSpeedProvider(_key(connection.credential_reference))
                ).sync(
                    connection.id,
                    args.target,
                    FormFactor(args.form_factor),
                    ExperienceScope(args.scope),
                )
                output = {"run_id": str(run.id), "status": run.status.value}
            else:
                rows = session.scalars(
                    select(ExperienceObservation)
                    .order_by(ExperienceObservation.observed_at.desc())
                    .limit(args.limit)
                ).all()
                output = [
                    {
                        "id": str(row.id),
                        "target": row.normalized_target,
                        "metric": row.metric.value,
                        "value": str(row.metric_value) if row.metric_value is not None else None,
                        "availability": row.availability.value,
                    }
                    for row in rows
                ]
        print(json.dumps(output))
        return 0
    except ValueError as error:
        print(json.dumps({"error": str(error)}))
        return 2


def main() -> None:
    raise SystemExit(run())
