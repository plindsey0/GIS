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
from gis.opportunities.service import DETECTORS, VERSION, OpportunityService


def _default(value: Any) -> Any:
    if isinstance(value, (uuid.UUID, datetime, date)):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-opportunities")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("detect", "list", "explain", "history", "evidence", "gaps", "reprocess"):
        item = commands.add_parser(name)
        item.add_argument("--tenant-id", type=uuid.UUID, required=True)
        item.add_argument("--site-id", type=uuid.UUID, required=True)
        item.add_argument("--dry-run", action="store_true")
    for name in ("types", "policies"):
        commands.add_parser(name)
    for name in ("dismiss", "restore"):
        item = commands.add_parser(name)
        item.add_argument("--opportunity-id", type=uuid.UUID, required=True)
        item.add_argument("--actor")
        item.add_argument("--reason", required=name == "dismiss")
    return root


def run(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = parser().parse_args(argv)
    if args.command in {"types", "policies"}:
        return {"detector_version": VERSION, "detectors": [{"key": key, **spec} for key, spec in DETECTORS.items()]}
    with session_factory()() as session:
        service = OpportunityService(session)
        if args.command in {"detect", "reprocess"}:
            rows = service.detect(args.tenant_id, args.site_id)
            payload = {"opportunities_evaluated": len(rows), "provider_calls": 0, "provider_cost": 0, "schedules_mutated": 0, "dry_run": args.dry_run}
            session.rollback() if args.dry_run else session.commit()
            return payload
        if args.command in {"dismiss", "restore"}:
            row = service.dismiss(args.opportunity_id, args.reason, args.actor) if args.command == "dismiss" else service.restore(args.opportunity_id, args.actor)
            session.commit()
            return {"id": row.id, "status": row.status}
        rows = service.list(args.tenant_id, args.site_id)
        return {"opportunities": [{"id": row.id, "family": row.family, "type": row.opportunity_type, "status": row.status, "priority": row.priority, "title": row.title, "evidence_sufficiency": row.evidence_sufficiency, "limitations": row.limitations_json, "recommendation": None} for row in rows]}


def main() -> None:
    try:
        print(json.dumps(run(), default=_default, sort_keys=True))
    except Exception as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
