from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.db import session_factory
from gis.emerging_demand.service import EmergingDemandService
from gis.models import DemandAnalysisRun, DemandSignal, DemandSignalType, DemandValidationRequest


def _json_default(value: Any) -> Any:
    if isinstance(value, (uuid.UUID, datetime, date, Decimal)):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"cannot serialize {type(value).__name__}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-emerging-demand")
    commands = root.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze")
    analyze.add_argument("--tenant-id", type=uuid.UUID, required=True)
    analyze.add_argument("--site-id", type=uuid.UUID, required=True)
    analyze.add_argument("--market-id", type=uuid.UUID, required=True)
    analyze.add_argument("--dry-run", action="store_true")
    for name in (
        "inspect",
        "trends",
        "emerging",
        "accelerating",
        "declining",
        "spikes",
        "segments",
        "market",
        "history",
        "evidence",
        "validation-requests",
        "estimate",
    ):
        command = commands.add_parser(name)
        command.add_argument("--tenant-id", type=uuid.UUID, required=True)
        command.add_argument("--site-id", type=uuid.UUID, required=True)
    reprocess = commands.add_parser("reprocess")
    reprocess.add_argument("--tenant-id", type=uuid.UUID, required=True)
    reprocess.add_argument("--site-id", type=uuid.UUID, required=True)
    reprocess.add_argument("--market-id", type=uuid.UUID, required=True)
    reprocess.add_argument("--dry-run", action="store_true")
    return root


def run(argv: Sequence[str] | None = None, session: Session | None = None) -> dict[str, Any]:
    args = parser().parse_args(argv)
    owns = session is None
    active = session or session_factory()()
    try:
        service = EmergingDemandService(active)
        if args.command in {"analyze", "reprocess"}:
            from gis.models import MarketDefinition

            market = active.get(MarketDefinition, args.market_id)
            if not market:
                raise ValueError("market definition not found")
            materialized = service.materialize_stored_evidence(market)
            result = service.analyze(args.tenant_id, args.site_id, args.market_id)
            payload: dict[str, Any] = {
                "analysis_run_id": result.id,
                "observation_count": result.observation_count,
                "signal_count": result.signal_count,
                "policy_version": result.policy_version,
                "dry_run": args.dry_run,
                "provider_calls": 0,
                "schedules_mutated": 0,
                "stored_observations_materialized": materialized,
            }
            active.rollback() if args.dry_run else active.commit()
            return payload
        if args.command == "validation-requests":
            requests = active.scalars(
                select(DemandValidationRequest)
                .join(DemandSignal)
                .join(DemandAnalysisRun)
                .where(
                    DemandAnalysisRun.tenant_id == args.tenant_id,
                    DemandAnalysisRun.site_id == args.site_id,
                )
            ).all()
            return {
                "requests": [
                    {
                        "id": row.id,
                        "target_id": row.collection_target_id,
                        "reason": row.reason,
                        "capability": row.desired_evidence_capability,
                        "urgency": row.urgency,
                        "status": row.status,
                        "expires_at": row.expires_at,
                    }
                    for row in requests
                ]
            }
        rows = service.inspect(args.tenant_id, args.site_id)
        filters = {
            "emerging": DemandSignalType.EMERGING,
            "accelerating": DemandSignalType.ACCELERATING,
            "declining": DemandSignalType.DECLINING,
            "spikes": DemandSignalType.SPIKE,
        }
        if args.command in filters:
            rows = [row for row in rows if row["classification"] is filters[args.command]]
        return {"command": args.command, "signals": rows, "provider_calls": 0}
    finally:
        if owns:
            active.close()


def main() -> None:
    try:
        print(json.dumps(run(), default=_json_default, sort_keys=True))
    except Exception as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
