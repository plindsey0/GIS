from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.db import session_factory
from gis.integrations.builtwith.provider import BuiltWithProvider
from gis.integrations.builtwith.service import BuiltWithCollector
from gis.integrations.builtwith.temporal import backfill_temporal
from gis.integrations.serp.cli import _scope
from gis.models import (
    ConnectionStatus,
    ConnectionType,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
)
from gis.orchestration.reliability import ClassifiedFailure
from gis.provider_control.credentials import builtwith_credentials


def configure(
    session: Session, tenant_slug: str, site_slug: str, reference: str
) -> DataSourceConnection:
    if not reference.startswith("env:") or not reference[4:].isidentifier():
        raise ValueError("Use an env: credential reference, not a secret value")
    tenant, site = _scope(session, tenant_slug, site_slug)
    source = session.scalar(select(DataSource).where(DataSource.key == "builtwith"))
    if source is None:
        raise ValueError("Seed the BuiltWith source first")
    connection = session.scalar(
        select(DataSourceConnection).where(
            DataSourceConnection.tenant_id == tenant.id,
            DataSourceConnection.site_id == site.id,
            DataSourceConnection.data_source_id == source.id,
        )
    )
    if connection is None:
        rights = DataRightsPolicy(
            tenant_id=tenant.id,
            name=f"BuiltWith {site.slug} — unreviewed",
            policy_version="1",
            effective_at=datetime.now(timezone.utc),
            documented_basis="API documentation: https://api.builtwith.com/domain-api. API accessibility establishes no downstream permission.",
            policy_notes="All uses UNKNOWN pending operator license review. Review authority and reviewed_at intentionally unset.",
        )
        session.add(rights)
        session.flush()
        connection = DataSourceConnection(
            tenant_id=tenant.id,
            site_id=site.id,
            data_source_id=source.id,
            connection_type=ConnectionType.LICENSED_ENRICHMENT,
            rights_policy_id=rights.id,
        )
        session.add(connection)
    connection.credential_reference = reference
    connection.status = ConnectionStatus.ACTIVE
    session.commit()
    return connection


def run(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gis-builtwith")
    commands = parser.add_subparsers(dest="command", required=True)
    config = commands.add_parser("configure")
    config.add_argument("--tenant", required=True)
    config.add_argument("--site", required=True)
    config.add_argument("--credential-reference", default="env:GIS_BUILTWITH_CREDENTIAL")
    sync = commands.add_parser("sync")
    sync.add_argument("--connection", type=uuid.UUID, required=True)
    sync.add_argument("--site", type=uuid.UUID, required=True)
    sync.add_argument("--domain", required=True)
    backfill = commands.add_parser("backfill-temporal")
    backfill.add_argument("--tenant", required=True)
    backfill.add_argument("--site", required=True)
    backfill.add_argument("--apply", action="store_true")
    args = parser.parse_args(arguments)
    try:
        with session_factory()() as session:
            if args.command == "configure":
                connection = configure(session, args.tenant, args.site, args.credential_reference)
                print(
                    json.dumps(
                        {
                            "connection_id": str(connection.id),
                            "authentication": "NOT_VALIDATED",
                            "collection": "NOT_ACTIVATED",
                        }
                    )
                )
            elif args.command == "sync":
                selected_connection = session.get(DataSourceConnection, args.connection)
                key = builtwith_credentials(
                    selected_connection.credential_reference if selected_connection else None
                )
                result = BuiltWithCollector(session, BuiltWithProvider(key)).sync(
                    args.connection, args.site, args.domain
                )
                print(
                    json.dumps({"ingestion_run_id": str(result.id), "status": result.status.value})
                )
                return 0 if result.status.value == "SUCCEEDED" and not result.error_count else 1
            else:
                tenant, site = _scope(session, args.tenant, args.site)
                print(json.dumps(backfill_temporal(session, tenant.id, site.id, apply=args.apply)))
        return 0
    except ClassifiedFailure as error:
        print(
            json.dumps(
                {
                    "failure_category": error.category.value,
                    "error_class": type(error).__name__,
                    "error": str(error),
                }
            )
        )
        return 1
    except ValueError:
        print(
            json.dumps(
                {
                    "failure_category": "CONFIGURATION_ERROR",
                    "error": "BuiltWith configuration or request is invalid",
                }
            )
        )
        return 1
    except Exception:
        print(
            json.dumps(
                {
                    "failure_category": "INTERNAL_PROCESSING_ERROR",
                    "error": "BuiltWith internal processing failed",
                }
            )
        )
        return 1


def main() -> None:
    raise SystemExit(run())
