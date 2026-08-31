from __future__ import annotations

import argparse
import enum
import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from gis.db import session_factory
from gis.market_intelligence.service import MAX_MARKET_MEMBERS, MarketIntelligenceService
from gis.models import (
    DataRightsPolicy,
    MarketDefinition,
    MarketDefinitionMember,
    MarketMetricObservation,
    MarketObservation,
    MarketParticipantObservation,
    MarketSegmentObservation,
    MarketType,
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


def _row(item: Any) -> dict[str, object]:
    mapper = item.__mapper__
    return {
        column.name: getattr(item, mapper.get_property_by_column(column).key)
        for column in item.__table__.columns
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-market-intelligence")
    commands = root.add_subparsers(dest="command", required=True)
    define = commands.add_parser("define")
    define.add_argument("--tenant", required=True)
    define.add_argument("--site", required=True)
    define.add_argument("--name", required=True)
    define.add_argument("--slug", required=True)
    define.add_argument(
        "--market-type", choices=[item.value for item in MarketType], default="SEARCH_MARKET"
    )
    define.add_argument("--tracked-query", type=uuid.UUID, action="append", required=True)
    define.add_argument("--description")
    define.add_argument("--created-by")
    define.add_argument("--dry-run", action="store_true")
    for name in ("list", "history"):
        command = commands.add_parser(name)
        command.add_argument("--tenant", required=True)
        command.add_argument("--site", required=True)
        command.add_argument("--limit", type=int, default=100)
    for name in ("inspect", "members", "validate"):
        command = commands.add_parser(name)
        command.add_argument("definition_id", type=uuid.UUID)
    estimate = commands.add_parser("estimate")
    estimate.add_argument("--members", type=int, required=True)
    estimate.add_argument("--dates", type=int, default=1)
    for name in ("observe", "build"):
        command = commands.add_parser(name)
        command.add_argument("definition_id", type=uuid.UUID)
        command.add_argument("--date", type=date.fromisoformat, required=True)
        command.add_argument("--rights-policy", type=uuid.UUID, required=True)
        command.add_argument("--dry-run", action="store_true")
    for name, model in (
        ("participants", MarketParticipantObservation),
        ("visibility", MarketParticipantObservation),
        ("segments", MarketSegmentObservation),
        ("structure", MarketMetricObservation),
        ("coverage", MarketObservation),
        ("compare", MarketObservation),
    ):
        command = commands.add_parser(name)
        command.add_argument("observation_id", type=uuid.UUID)
        command.set_defaults(model=model)
    return root


def _scope(session: Any, tenant_slug: str, site_slug: str) -> tuple[Tenant, Site]:
    tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    site = (
        session.scalar(select(Site).where(Site.tenant_id == tenant.id, Site.slug == site_slug))
        if tenant
        else None
    )
    if not tenant or not site:
        raise ValueError("tenant/site not found")
    return tenant, site


def run(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    if args.command == "estimate":
        if not 1 <= args.members <= MAX_MARKET_MEMBERS or not 1 <= args.dates <= 366:
            raise ValueError("members must be 1..500 and dates must be 1..366")
        emit(
            {
                "members": args.members,
                "dates": args.dates,
                "estimated_provider_cost": "0",
                "provider_calls": 0,
                "bounded": True,
            }
        )
        return 0
    with session_factory()() as session:
        service = MarketIntelligenceService(session)
        if args.command == "define":
            tenant, site = _scope(session, args.tenant, args.site)
            if args.dry_run:
                preview = service.define(
                    tenant_id=tenant.id,
                    site_id=site.id,
                    name=args.name,
                    slug=args.slug,
                    tracked_query_ids=args.tracked_query,
                    market_type=MarketType(args.market_type),
                    description=args.description,
                    created_by=args.created_by,
                )
                preview_version = preview.version
                session.rollback()
                emit(
                    {
                        "valid": True,
                        "member_count": len(args.tracked_query),
                        "definition_version": preview_version,
                        "would_create_version": True,
                        "provider_calls": 0,
                    }
                )
                return 0
            created_definition = service.define(
                tenant_id=tenant.id,
                site_id=site.id,
                name=args.name,
                slug=args.slug,
                tracked_query_ids=args.tracked_query,
                market_type=MarketType(args.market_type),
                description=args.description,
                created_by=args.created_by,
            )
            session.commit()
            emit(_row(created_definition))
            return 0
        if args.command in {"list", "history"}:
            tenant, site = _scope(session, args.tenant, args.site)
            definition_rows = session.scalars(
                select(MarketDefinition)
                .where(MarketDefinition.tenant_id == tenant.id, MarketDefinition.site_id == site.id)
                .order_by(MarketDefinition.slug, MarketDefinition.version.desc())
                .limit(args.limit)
            ).all()
            emit([_row(item) for item in definition_rows])
            return 0
        if args.command in {"inspect", "members", "validate", "observe", "build"}:
            selected_definition = session.get(MarketDefinition, args.definition_id)
            if not selected_definition:
                raise ValueError("market definition not found")
            if args.command == "inspect":
                emit(_row(selected_definition))
                return 0
            if args.command == "members":
                member_rows = session.scalars(
                    select(MarketDefinitionMember)
                    .where(MarketDefinitionMember.market_definition_id == selected_definition.id)
                    .order_by(MarketDefinitionMember.rank_order)
                ).all()
                emit([_row(item) for item in member_rows])
                return 0
            if args.command == "validate":
                emit(service.validate(selected_definition))
                return 0
            policy = session.get(DataRightsPolicy, args.rights_policy)
            if not policy:
                raise ValueError("rights policy not found")
            if args.dry_run:
                preview_observation = service.observe(selected_definition, args.date, policy)
                preview_coverage = preview_observation.coverage_status
                preview_query_count = preview_observation.observed_query_count
                session.rollback()
                emit(
                    {
                        "definition_id": selected_definition.id,
                        "definition_version": selected_definition.version,
                        "date": args.date,
                        "estimated_provider_cost": "0",
                        "provider_calls": 0,
                        "would_persist": False,
                        "coverage_status": preview_coverage,
                        "observed_query_count": preview_query_count,
                    }
                )
                return 0
            created_observation = service.observe(selected_definition, args.date, policy)
            session.commit()
            emit(_row(created_observation))
            return 0
        selected_observation = session.get(MarketObservation, args.observation_id)
        if not selected_observation:
            raise ValueError("market observation not found")
        if args.model is MarketObservation:
            emit(_row(selected_observation))
            return 0
        rows = session.scalars(
            select(args.model).where(args.model.market_observation_id == selected_observation.id)
        ).all()
        emit([_row(item) for item in rows])
        return 0


def main() -> None:
    raise SystemExit(run())
