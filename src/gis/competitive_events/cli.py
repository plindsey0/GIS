from __future__ import annotations

import argparse
import enum
import json
import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import select

from gis.competitive_events.service import SynthesisService
from gis.db import session_factory
from gis.models import (
    CompetitiveEvent,
    CompetitiveEventDomain,
    CompetitiveEventEvidence,
    CompetitiveEventRelationship,
    CompetitiveEventType,
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
    root = argparse.ArgumentParser(prog="gis-competitive-events")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("synthesize", "reprocess"):
        command = commands.add_parser(name)
        command.add_argument("--tenant", required=True)
        command.add_argument("--site", required=True)
        command.add_argument("--start-date", type=date.fromisoformat, required=True)
        command.add_argument("--end-date", type=date.fromisoformat, required=True)
        command.add_argument(
            "--domains",
            nargs="*",
            choices=[item.value for item in CompetitiveEventDomain],
            default=[item.value for item in CompetitiveEventDomain],
        )
    for name in ("inspect", "evidence", "relationships"):
        command = commands.add_parser(name)
        command.add_argument("event_id", type=uuid.UUID)
    timeline = commands.add_parser("timeline")
    timeline.add_argument("--tenant", required=True)
    timeline.add_argument("--site", required=True)
    timeline.add_argument("--subject")
    timeline.add_argument("--domain", choices=[item.value for item in CompetitiveEventDomain])
    timeline.add_argument("--limit", type=int, default=100)
    commands.add_parser("types")
    return root


def event_json(event: CompetitiveEvent) -> dict[str, object]:
    return {
        column.name: getattr(event, column.key) for column in CompetitiveEvent.__table__.columns
    }


def run(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    if args.command == "types":
        emit(
            {
                "event_domains": [item.value for item in CompetitiveEventDomain],
                "event_types": [item.value for item in CompetitiveEventType],
            }
        )
        return 0
    with session_factory()() as session:
        if args.command in {"synthesize", "reprocess", "timeline"}:
            tenant = session.scalar(select(Tenant).where(Tenant.slug == args.tenant))
            if not tenant:
                raise ValueError("tenant not found")
            site = session.scalar(
                select(Site).where(Site.tenant_id == tenant.id, Site.slug == args.site)
            )
            if not site:
                raise ValueError("site not found in tenant")
            if args.command in {"synthesize", "reprocess"}:
                start = datetime.combine(args.start_date, time.min, timezone.utc)
                end = datetime.combine(args.end_date, time.max, timezone.utc)
                result = SynthesisService(session).synthesize(
                    tenant.id,
                    site.id,
                    [CompetitiveEventDomain(item) for item in args.domains],
                    start,
                    end,
                )
                session.commit()
                emit(result)
                return 0
            query = select(CompetitiveEvent).where(
                CompetitiveEvent.tenant_id == tenant.id, CompetitiveEvent.site_id == site.id
            )
            if args.subject:
                query = query.where(CompetitiveEvent.subject_key == args.subject)
            if args.domain:
                query = query.where(
                    CompetitiveEvent.event_domain == CompetitiveEventDomain(args.domain)
                )
            events = session.scalars(
                query.order_by(CompetitiveEvent.event_time.desc()).limit(args.limit)
            ).all()
            emit([event_json(item) for item in events])
            return 0
        event = session.get(CompetitiveEvent, args.event_id)
        if not event:
            raise ValueError("event not found")
        if args.command == "inspect":
            emit(event_json(event))
        elif args.command == "evidence":
            evidence_rows = session.scalars(
                select(CompetitiveEventEvidence).where(
                    CompetitiveEventEvidence.competitive_event_id == event.id
                )
            ).all()
            emit(
                [
                    {
                        column.name: getattr(row, column.key)
                        for column in CompetitiveEventEvidence.__table__.columns
                    }
                    for row in evidence_rows
                ]
            )
        else:
            relationship_rows = session.scalars(
                select(CompetitiveEventRelationship).where(
                    (CompetitiveEventRelationship.from_event_id == event.id)
                    | (CompetitiveEventRelationship.to_event_id == event.id)
                )
            ).all()
            emit(
                [
                    {
                        column.name: getattr(row, column.key)
                        for column in CompetitiveEventRelationship.__table__.columns
                    }
                    for row in relationship_rows
                ]
            )
    return 0


def main() -> None:
    raise SystemExit(run())
