from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

from sqlalchemy import select

from gis.db import session_factory
from gis.goals.service import GoalService
from gis.models import ObjectiveDerivation, StrategicObjective


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect governed GIS goals")
    parser.add_argument("command", choices=["list", "show", "explain", "map", "registry"])
    parser.add_argument("--tenant-id", type=uuid.UUID, required=True)
    parser.add_argument("--site-id", type=uuid.UUID, required=True)
    parser.add_argument("--id", type=uuid.UUID)
    args = parser.parse_args()
    with session_factory()() as session:
        service = GoalService(session)
        result: Any
        if args.command == "registry":
            result = [
                {
                    "key": key,
                    "name": value.name,
                    "source": value.source_system,
                    "unit": value.unit,
                    "measurable": value.currently_measurable,
                }
                for key, value in service.ensure_registry().items()
            ]
            session.commit()
        elif args.command == "list":
            result = [
                {
                    "id": str(row.id),
                    "name": row.name,
                    "level": row.level.value,
                    "lifecycle": row.lifecycle.value,
                    "measurement": row.measurement_health.value,
                    "decomposition": row.decomposition_state.value,
                }
                for row in session.scalars(
                    select(StrategicObjective).where(
                        StrategicObjective.tenant_id == args.tenant_id,
                        StrategicObjective.site_id == args.site_id,
                    )
                )
            ]
        elif args.command in {"show", "explain"}:
            if not args.id:
                parser.error("--id is required")
            row = service._objective(args.id, args.tenant_id, args.site_id)
            derivations = list(
                session.scalars(
                    select(ObjectiveDerivation)
                    .where(ObjectiveDerivation.source_objective_id == row.id)
                    .order_by(ObjectiveDerivation.executed_at.desc())
                )
            )
            result = {
                "id": str(row.id),
                "name": row.name,
                "state": row.lifecycle.value,
                "measurement": row.measurement_health.value,
                "decomposition": row.decomposition_state.value,
                "why": [
                    {
                        "rule": item.rule_key,
                        "version": item.rule_version,
                        "formula": item.formula,
                        "inputs": item.input_values_json,
                        "result": str(item.output_value) if item.output_value is not None else None,
                        "blocked_reason": item.blocked_reason,
                    }
                    for item in derivations
                ],
            }
        else:
            rows = list(
                session.scalars(
                    select(StrategicObjective).where(
                        StrategicObjective.tenant_id == args.tenant_id,
                        StrategicObjective.site_id == args.site_id,
                    )
                )
            )
            result = {"nodes": [{"id": str(row.id), "label": row.name} for row in rows]}
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
