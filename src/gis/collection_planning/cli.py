from __future__ import annotations

import argparse
import enum
import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.collection_planning.service import CollectionPlanningService
from gis.db import session_factory
from gis.models import (
    CollectionCadence,
    CollectionOverrideType,
    CollectionPlanItem,
    CollectionPlanningDecision,
    CollectionPlanningRun,
    CollectionPriorityTier,
    CollectionTarget,
    CollectionTargetOverride,
    CollectionTargetType,
    CollectorCapability,
    MarketDefinition,
)


def json_default(value: object) -> object:
    if isinstance(value, (uuid.UUID, date, datetime, Decimal)):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def emit(value: object) -> None:
    print(json.dumps(value, default=json_default, sort_keys=True))


def row(item: Any) -> dict[str, object]:
    mapper = item.__mapper__
    return {
        column.name: getattr(item, mapper.get_property_by_column(column).key)
        for column in item.__table__.columns
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-collection-planning")
    commands = root.add_subparsers(dest="command", required=True)
    discover = commands.add_parser("discover")
    discover.add_argument("market_id", type=uuid.UUID)
    discover.add_argument("--dry-run", action="store_true")
    for name in ("evaluate", "plan"):
        command = commands.add_parser(name)
        command.add_argument("market_id", type=uuid.UUID)
        command.add_argument("--dry-run", action="store_true")
    apply = commands.add_parser("apply")
    apply.add_argument("planning_run_id", type=uuid.UUID)
    apply.add_argument("--actor", required=True)
    apply.add_argument("--dry-run", action="store_true")
    seed = commands.add_parser("seed")
    seed.add_argument("market_id", type=uuid.UUID)
    seed.add_argument("--type", type=CollectionTargetType, required=True)
    seed.add_argument("--value", required=True)
    seed.add_argument("--actor", required=True)
    seed.add_argument("--reason", required=True)
    seed.add_argument("--dry-run", action="store_true")
    for name in ("inspect", "explain"):
        command = commands.add_parser(name)
        command.add_argument("target_id", type=uuid.UUID)
    for name in ("targets", "candidates"):
        command = commands.add_parser(name)
        command.add_argument("market_id", type=uuid.UUID)
        command.add_argument("--limit", type=int, default=500)
    history = commands.add_parser("history")
    history.add_argument("target_id", type=uuid.UUID)
    for name in ("costs", "blockers"):
        command = commands.add_parser(name)
        command.add_argument("planning_run_id", type=uuid.UUID)
    commands.add_parser("collectors")
    override = commands.add_parser("override")
    override.add_argument("target_id", type=uuid.UUID)
    override.add_argument("--type", type=CollectionOverrideType, required=True)
    override.add_argument("--priority", type=CollectionPriorityTier)
    override.add_argument("--cadence", type=CollectionCadence)
    override.add_argument("--capability-id", type=uuid.UUID)
    override.add_argument("--actor", required=True)
    override.add_argument("--reason", required=True)
    clear = commands.add_parser("clear-override")
    clear.add_argument("target_id", type=uuid.UUID)
    clear.add_argument("--actor", required=True)
    return root


def _market(session: Session, market_id: uuid.UUID) -> MarketDefinition:
    market = session.get(MarketDefinition, market_id)
    if not market:
        raise ValueError("market definition not found")
    return market


def _target(session: Session, target_id: uuid.UUID) -> CollectionTarget:
    target = session.get(CollectionTarget, target_id)
    if not target:
        raise ValueError("collection target not found")
    return target


def run(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    with session_factory()() as session:
        service = CollectionPlanningService(session)
        if args.command == "discover":
            targets = service.discover(_market(session, args.market_id))
            discovery_payload = {"discovered_or_updated": len(targets), "provider_calls": 0}
            session.rollback() if args.dry_run else session.commit()
            emit({**discovery_payload, "persisted": not args.dry_run})
            return 0
        if args.command in {"evaluate", "plan"}:
            proposed_run = service.plan(_market(session, args.market_id))
            plan_payload = row(proposed_run)
            session.rollback() if args.dry_run else session.commit()
            emit({**plan_payload, "persisted": not args.dry_run, "provider_calls": 0})
            return 0
        if args.command == "apply":
            planning_run = session.get(CollectionPlanningRun, args.planning_run_id)
            if not planning_run:
                raise ValueError("planning run not found")
            items = service.apply(planning_run, args.actor)
            session.rollback() if args.dry_run else session.commit()
            emit(
                {
                    "planning_run_id": planning_run.id,
                    "reconciled_items": len(items),
                    "persisted": not args.dry_run,
                    "schedules_enabled": 0,
                }
            )
            return 0
        if args.command == "seed":
            target = service.seed_target(
                _market(session, args.market_id), args.type, args.value, args.actor, args.reason
            )
            target_payload = row(target)
            session.rollback() if args.dry_run else session.commit()
            emit({**target_payload, "persisted": not args.dry_run})
            return 0
        if args.command == "inspect":
            emit(row(_target(session, args.target_id)))
            return 0
        if args.command == "explain":
            emit(service.explain(_target(session, args.target_id)))
            return 0
        if args.command in {"targets", "candidates"}:
            target_statement = (
                select(CollectionTarget)
                .where(CollectionTarget.market_definition_id == args.market_id)
                .order_by(CollectionTarget.normalized_identity)
                .limit(min(max(args.limit, 1), 5000))
            )
            if args.command == "candidates":
                from gis.models import CollectionTargetStatus

                target_statement = target_statement.where(
                    CollectionTarget.status == CollectionTargetStatus.CANDIDATE
                )
            emit([row(item) for item in session.scalars(target_statement).all()])
            return 0
        if args.command == "history":
            target = _target(session, args.target_id)
            decisions = session.scalars(
                select(CollectionPlanningDecision)
                .where(CollectionPlanningDecision.target_id == target.id)
                .order_by(CollectionPlanningDecision.evaluated_at.desc())
            ).all()
            overrides = session.scalars(
                select(CollectionTargetOverride)
                .where(CollectionTargetOverride.target_id == target.id)
                .order_by(CollectionTargetOverride.created_at.desc())
            ).all()
            emit(
                {
                    "target": row(target),
                    "decisions": [row(item) for item in decisions],
                    "overrides": [row(item) for item in overrides],
                }
            )
            return 0
        if args.command in {"costs", "blockers"}:
            plan_item_statement = (
                select(CollectionPlanItem)
                .join(
                    CollectionPlanningDecision,
                    CollectionPlanningDecision.id == CollectionPlanItem.decision_id,
                )
                .where(CollectionPlanningDecision.planning_run_id == args.planning_run_id)
            )
            if args.command == "blockers":
                from gis.models import CollectionBlocker

                plan_item_statement = plan_item_statement.where(
                    CollectionPlanItem.blocker != CollectionBlocker.NONE
                )
            plan_items = session.scalars(plan_item_statement).all()
            emit(
                {
                    "items": [row(item) for item in plan_items],
                    "known_monthly_cost": str(
                        sum(
                            (
                                item.estimated_monthly_cost
                                for item in plan_items
                                if item.estimated_monthly_cost is not None
                            ),
                            Decimal(0),
                        )
                    ),
                    "unknown_cost_items": sum(
                        1 for item in plan_items if item.estimated_monthly_cost is None
                    ),
                }
            )
            return 0
        if args.command == "collectors":
            service.ensure_collectors()
            session.flush()
            rows = session.scalars(
                select(CollectorCapability).order_by(
                    CollectorCapability.target_type, CollectorCapability.preference
                )
            ).all()
            session.rollback()
            emit([row(item) for item in rows])
            return 0
        if args.command == "override":
            target = _target(session, args.target_id)
            override = service.set_override(
                target,
                args.type,
                args.actor,
                args.reason,
                priority=args.priority,
                cadence=args.cadence,
                capability_id=args.capability_id,
            )
            session.commit()
            emit(row(override))
            return 0
        if args.command == "clear-override":
            cleared = service.clear_override(_target(session, args.target_id), args.actor)
            session.commit()
            emit({"cleared": bool(cleared), "override_id": cleared.id if cleared else None})
            return 0
    return 1


def main() -> None:
    raise SystemExit(run())
