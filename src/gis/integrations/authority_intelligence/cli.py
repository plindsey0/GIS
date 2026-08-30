from __future__ import annotations

import argparse
import enum
import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.db import session_factory
from gis.integrations.authority_intelligence.provider import (
    MAX_PAGES,
    MAX_ROWS,
    AuthorityRequest,
    JSONFixtureAuthorityProvider,
)
from gis.integrations.authority_intelligence.service import AuthorityCollector
from gis.models import (
    AuthorityMetricObservation,
    AuthorityObservation,
    AuthorityTargetType,
    BacklinkObservation,
    DataSourceConnection,
    ReferringDomainObservation,
    Site,
    Tenant,
)


def json_default(value: object) -> object:
    if isinstance(value, (uuid.UUID, datetime, date, Decimal)):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def emit(value: object) -> None:
    print(json.dumps(value, default=json_default, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-authority-intelligence")
    commands = root.add_subparsers(dest="command", required=True)
    configure = commands.add_parser("configure")
    configure.add_argument("--connection", type=uuid.UUID, required=True)
    configure.add_argument("--provider", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--fixture", type=Path, required=True)
    estimate = commands.add_parser("estimate")
    estimate.add_argument("--targets", type=int, required=True)
    estimate.add_argument("--rows", type=int, default=1000)
    estimate.add_argument("--pages", type=int, default=10)
    estimate.add_argument("--unit-cost", type=Decimal, default=Decimal("0"))
    collect = commands.add_parser("collect")
    collect.add_argument("--tenant", required=True)
    collect.add_argument("--site", required=True)
    collect.add_argument("--connection", type=uuid.UUID, required=True)
    collect.add_argument(
        "--target-type", choices=[item.value for item in AuthorityTargetType], required=True
    )
    collect.add_argument("--target", required=True)
    collect.add_argument("--rows", type=int, default=1000)
    collect.add_argument("--pages", type=int, default=10)
    collect.add_argument("--fixture", type=Path, required=True)
    collect.add_argument("--estimated-cost", type=Decimal, default=Decimal("0"))
    collect.add_argument("--retain-raw-anchor", action="store_true")
    collect.add_argument("--dry-run", action="store_true")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("observation_id", type=uuid.UUID)
    for name, model in (
        ("backlinks", BacklinkObservation),
        ("referring-domains", ReferringDomainObservation),
        ("domains", AuthorityObservation),
        ("pages", AuthorityObservation),
        ("competitors", AuthorityObservation),
        ("compare", AuthorityObservation),
        ("changes", AuthorityObservation),
    ):
        command = commands.add_parser(name)
        command.set_defaults(model=model)
        command.add_argument("--tenant", required=True)
        command.add_argument("--site", required=True)
        command.add_argument("--limit", type=int, default=100)
    return root


def _row(item: Any) -> dict[str, object]:
    return {column.name: getattr(item, column.key) for column in item.__table__.columns}


def _scope(session: Session, tenant_slug: str, site_slug: str) -> tuple[Tenant, Site]:
    tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    site = (
        session.scalar(select(Site).where(Site.tenant_id == tenant.id, Site.slug == site_slug))
        if tenant
        else None
    )
    if not tenant or not site:
        raise ValueError("tenant/site not found")
    return tenant, site


def estimate_cost(targets: int, rows: int, pages: int, unit_cost: Decimal) -> Decimal:
    if not 1 <= targets <= 25:
        raise ValueError("targets must be between 1 and 25")
    AuthorityRequest(AuthorityTargetType.DOMAIN, "example.com", rows, pages).validate()
    return Decimal(targets) * unit_cost


def run(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    if args.command == "estimate":
        emit(
            {
                "targets": args.targets,
                "row_limit": args.rows,
                "page_limit": args.pages,
                "hard_row_max": MAX_ROWS,
                "hard_page_max": MAX_PAGES,
                "estimated_cost": estimate_cost(
                    args.targets, args.rows, args.pages, args.unit_cost
                ),
                "paid_request_performed": False,
            }
        )
        return 0
    if args.command == "validate":
        request = AuthorityRequest(AuthorityTargetType.DOMAIN, "example.com")
        collection = JSONFixtureAuthorityProvider(args.fixture).collect(request)
        emit(
            {
                "valid": True,
                "provider": collection.provider,
                "metrics": len(collection.metrics),
                "backlinks": len(collection.backlinks),
                "paid_request_performed": False,
            }
        )
        return 0
    with session_factory()() as session:
        if args.command == "configure":
            connection = session.get(DataSourceConnection, args.connection)
            if not connection:
                raise ValueError("connection not found")
            connection.configuration_json = {
                **connection.configuration_json,
                "authority_provider": args.provider.casefold(),
            }
            session.commit()
            emit(
                {
                    "connection_id": connection.id,
                    "provider": args.provider.casefold(),
                    "credentials_stored": False,
                }
            )
            return 0
        if args.command == "collect":
            tenant, site = _scope(session, args.tenant, args.site)
            request = AuthorityRequest(
                AuthorityTargetType(args.target_type),
                args.target,
                args.rows,
                args.pages,
                retain_raw_anchor=args.retain_raw_anchor,
            )
            request.validate()
            if args.dry_run:
                emit(
                    {
                        "tenant_id": tenant.id,
                        "site_id": site.id,
                        "connection_id": args.connection,
                        "target": args.target,
                        "target_type": args.target_type,
                        "row_limit": args.rows,
                        "page_limit": args.pages,
                        "estimated_cost": args.estimated_cost,
                        "paid_request_performed": False,
                    }
                )
                return 0
            run_item = AuthorityCollector(
                session, JSONFixtureAuthorityProvider(args.fixture)
            ).collect(args.connection, site.id, request, estimated_cost=args.estimated_cost)
            emit(
                {
                    "ingestion_run_id": run_item.id,
                    "status": run_item.status,
                    "records_received": run_item.records_received,
                    "records_inserted": run_item.records_inserted,
                    "records_updated": run_item.records_updated,
                    "error_summary": run_item.error_summary,
                }
            )
            return 0
        if args.command == "inspect":
            observation = session.get(AuthorityObservation, args.observation_id)
            if not observation:
                raise ValueError("observation not found")
            metrics = session.scalars(
                select(AuthorityMetricObservation).where(
                    AuthorityMetricObservation.authority_observation_id == observation.id
                )
            ).all()
            emit({"observation": _row(observation), "metrics": [_row(item) for item in metrics]})
            return 0
        tenant, site = _scope(session, args.tenant, args.site)
        if args.command in {"backlinks", "referring-domains"}:
            model = (
                BacklinkObservation if args.command == "backlinks" else ReferringDomainObservation
            )
            rows = session.scalars(
                select(model)
                .join(
                    AuthorityObservation, model.authority_observation_id == AuthorityObservation.id
                )
                .where(
                    AuthorityObservation.tenant_id == tenant.id,
                    AuthorityObservation.site_id == site.id,
                )
                .limit(args.limit)
            ).all()
        else:
            query = select(AuthorityObservation).where(
                AuthorityObservation.tenant_id == tenant.id, AuthorityObservation.site_id == site.id
            )
            if args.command == "pages":
                query = query.where(AuthorityObservation.target_type == AuthorityTargetType.PAGE)
            elif args.command == "domains":
                query = query.where(AuthorityObservation.target_type == AuthorityTargetType.DOMAIN)
            rows = session.scalars(
                query.order_by(AuthorityObservation.observed_at.desc()).limit(args.limit)
            ).all()
        emit([_row(item) for item in rows])
    return 0


def main() -> None:
    raise SystemExit(run())
