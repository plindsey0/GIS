from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Sequence
from datetime import date, datetime
from enum import Enum
from typing import Any

from gis.db import session_factory
from gis.interventions.service import METRICS, TYPES, VERSION, InterventionService
from gis.models import InterventionStatus


def default(value: Any) -> Any:
    if isinstance(value, (uuid.UUID, datetime, date)):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-interventions")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("types")
    commands.add_parser("metrics")
    for name in ("list", "inspect", "history", "outcomes", "blockers", "measurement-readiness"):
        item = commands.add_parser(name)
        item.add_argument("--tenant-id", type=uuid.UUID, required=True)
        item.add_argument("--site-id", type=uuid.UUID, required=True)
    for name in ("propose", "approve", "reject", "cancel", "start", "complete"):
        item = commands.add_parser(name)
        item.add_argument("--intervention-id", type=uuid.UUID, required=True)
        item.add_argument("--actor")
        item.add_argument("--reason")
        item.add_argument("--dry-run", action="store_true")
    baseline = commands.add_parser("baseline")
    baseline.add_argument("--intervention-id", type=uuid.UUID, required=True)
    return root


def run(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = parser().parse_args(argv)
    if args.command == "types":
        return {
            "version": VERSION,
            "types": [{"key": key, **spec} for key, spec in TYPES.items()],
            "human_approval_required": True,
        }
    if args.command == "metrics":
        return {
            "version": VERSION,
            "metrics": [
                {"key": key, "name": value[0], "source": value[1], "unit": value[2]}
                for key, value in METRICS.items()
            ],
        }
    with session_factory()() as session:
        service = InterventionService(session)
        if args.command == "baseline":
            return service.baseline(args.intervention_id)
        if args.command in {"propose", "approve", "reject", "cancel", "start", "complete"}:
            targets = {
                "propose": InterventionStatus.PROPOSED,
                "approve": InterventionStatus.APPROVED,
                "reject": InterventionStatus.REJECTED,
                "cancel": InterventionStatus.CANCELLED,
                "start": InterventionStatus.IN_PROGRESS,
                "complete": InterventionStatus.COMPLETED,
            }
            row = service.transition(
                args.intervention_id, targets[args.command], actor=args.actor, reason=args.reason
            )
            session.rollback() if args.dry_run else session.commit()
            return {
                "id": row.id,
                "status": row.status,
                "dry_run": args.dry_run,
                "autonomous_execution": False,
            }
        rows = service.list(args.tenant_id, args.site_id)
        return {
            "interventions": [
                {
                    "id": row.id,
                    "title": row.title,
                    "status": row.status,
                    "feasibility": row.feasibility,
                    "measurement_readiness": row.measurement_readiness,
                    "opportunity_id": row.primary_opportunity_id,
                    "causal_attribution": False,
                }
                for row in rows
            ]
        }


def main() -> None:
    try:
        print(json.dumps(run(), default=default, sort_keys=True))
    except Exception as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
