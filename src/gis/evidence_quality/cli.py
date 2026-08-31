from __future__ import annotations

import argparse
import enum
import json
import sys
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from gis.db import session_factory
from gis.evidence_quality.service import EvidenceQualityService
from gis.models import (
    AnalyticalEntityType,
    EvidenceContract,
    EvidenceGap,
    EvidencePackage,
    IdentityRelationship,
    ResolutionStrength,
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
    return {
        column.name: getattr(item, item.__mapper__.get_property_by_column(column).key)
        for column in item.__table__.columns
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-evidence-quality")
    commands = root.add_subparsers(dest="command", required=True)
    resolve = commands.add_parser("resolve")
    resolve.add_argument("--tenant-id", type=uuid.UUID, required=True)
    resolve.add_argument("--site-id", type=uuid.UUID, required=True)
    resolve.add_argument(
        "--type", choices=[item.value for item in AnalyticalEntityType], required=True
    )
    resolve.add_argument("--value", required=True)
    resolve.add_argument("--other-value")
    resolve.add_argument("--relationship", choices=[item.value for item in IdentityRelationship])
    resolve.add_argument("--dry-run", action="store_true")
    assess = commands.add_parser("assess")
    assess.add_argument("--tenant-id", type=uuid.UUID, required=True)
    assess.add_argument("--site-id", type=uuid.UUID, required=True)
    assess.add_argument("--dry-run", action="store_true")
    for name in ("inspect", "package", "explain"):
        command = commands.add_parser(name)
        command.add_argument("package_id", type=uuid.UUID)
    for name in (
        "conflicts",
        "corroboration",
        "gaps",
        "contracts",
        "history",
        "compare",
        "reprocess",
    ):
        command = commands.add_parser(name)
        command.add_argument("--tenant-id", type=uuid.UUID, required=True)
        command.add_argument("--site-id", type=uuid.UUID, required=True)
    return root


def run(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    with session_factory()() as session:
        service = EvidenceQualityService(session)
        if args.command == "resolve":
            entity_type = AnalyticalEntityType(args.type)
            entity = service.entity(args.tenant_id, args.site_id, entity_type, args.value)
            assertion = None
            if args.other_value:
                if entity_type is AnalyticalEntityType.DOMAIN:
                    assertion = service.resolve_domains(
                        args.tenant_id, args.site_id, args.value, args.other_value
                    )
                elif entity_type is AnalyticalEntityType.URL and args.relationship:
                    assertion = service.resolve_urls(
                        args.tenant_id,
                        args.site_id,
                        args.value,
                        args.other_value,
                        IdentityRelationship(args.relationship),
                        {"operator_supplied_evidence_reference": True},
                    )
                else:
                    other = service.entity(
                        args.tenant_id, args.site_id, entity_type, args.other_value
                    )
                    assertion = service.assert_identity(
                        entity,
                        other,
                        IdentityRelationship.RELATED_NOT_IDENTICAL,
                        ResolutionStrength.UNRESOLVED,
                        "EXPLICIT_NON_SEMANTIC_COMPARISON_V1",
                        {"semantic_matching_performed": False},
                    )
            session.rollback() if args.dry_run else session.commit()
            emit(
                {
                    "entity": row(entity),
                    "assertion": row(assertion) if assertion else None,
                    "persisted": not args.dry_run,
                    "provider_calls": 0,
                }
            )
            return 0
        if args.command in {"assess", "reprocess"}:
            result = service.assess(args.tenant_id, args.site_id)
            dry_run = bool(getattr(args, "dry_run", False))
            session.rollback() if dry_run else session.commit()
            emit(
                {
                    **row(result),
                    "persisted": not dry_run,
                    "provider_calls": 0,
                    "schedules_mutated": 0,
                }
            )
            return 0
        if args.command in {"inspect", "package", "explain"}:
            emit(service.explain(args.package_id))
            return 0
        if args.command == "contracts":
            service.ensure_contracts()
            rows = session.scalars(
                select(EvidenceContract).order_by(EvidenceContract.contract_key)
            ).all()
            session.rollback()
            emit([row(item) for item in rows])
            return 0
        statement = select(EvidencePackage).where(
            EvidencePackage.tenant_id == args.tenant_id,
            EvidencePackage.site_id == args.site_id,
        )
        if args.command == "conflicts":
            statement = statement.where(EvidencePackage.conflict_count > 0)
        elif args.command == "corroboration":
            statement = statement.where(EvidencePackage.independent_source_count > 1)
        elif args.command == "gaps":
            gaps = session.scalars(
                select(EvidenceGap)
                .join(EvidencePackage)
                .where(
                    EvidencePackage.tenant_id == args.tenant_id,
                    EvidencePackage.site_id == args.site_id,
                )
            ).all()
            emit([row(item) for item in gaps])
            return 0
        emit([row(item) for item in session.scalars(statement).all()])
        return 0
    return 1


def main() -> None:
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
