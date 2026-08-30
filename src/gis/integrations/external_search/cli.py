from __future__ import annotations

import argparse
import json
import uuid
from decimal import Decimal

from sqlalchemy import select

from gis.db import session_factory
from gis.integrations.external_search.dataforseo import (
    DataForSEOExternalSearchProvider,
    SearchRequest,
)
from gis.integrations.external_search.service import ExternalSearchCollector
from gis.integrations.serp.cli import _credentials, configure_connection
from gis.models import DataSourceConnection, ExternalSearchObservation, Site

DEFAULT_TASK_COST = Decimal("0.012")
DEFAULT_ITEM_COST = Decimal("0.00012")


def estimate_cost(
    limit: int,
    *,
    task_cost: Decimal = DEFAULT_TASK_COST,
    item_cost: Decimal = DEFAULT_ITEM_COST,
) -> Decimal:
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    return (task_cost + item_cost * limit).quantize(Decimal("0.00000001"))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-search-intelligence")
    commands = root.add_subparsers(dest="command", required=True)
    configure = commands.add_parser("configure")
    configure.add_argument("--tenant", required=True)
    configure.add_argument("--site", required=True)
    configure.add_argument("--credential-reference", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--connection", type=uuid.UUID, required=True)
    for name in ("sync", "keywords", "competitors"):
        command = commands.add_parser(name)
        command.add_argument("--connection", type=uuid.UUID, required=True)
        command.add_argument("--site", type=uuid.UUID, required=True)
        command.add_argument("--domain", required=True)
        command.add_argument("--location-code", type=int)
        command.add_argument("--location-name")
        command.add_argument("--country")
        command.add_argument("--language", default="en")
        command.add_argument("--device")
        command.add_argument("--limit", type=int, default=100)
        command.add_argument("--kind", choices=("ranked_keywords", "competitors"))
        command.add_argument("--dry-run", action="store_true")
    estimate = commands.add_parser("estimate")
    estimate.add_argument("--limit", type=int, required=True)
    estimate.add_argument("--task-cost", type=Decimal, default=DEFAULT_TASK_COST)
    estimate.add_argument("--item-cost", type=Decimal, default=DEFAULT_ITEM_COST)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--limit", type=int, default=20)
    return root


def run(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    try:
        with session_factory()() as session:
            if args.command == "configure":
                configured = configure_connection(
                    session, args.tenant, args.site, args.credential_reference
                )
                output: object = {
                    "connection_id": str(configured.id),
                    "status": configured.status.value,
                }
            elif args.command == "validate":
                validated = session.get(DataSourceConnection, args.connection)
                if not validated:
                    raise ValueError("connection not found")
                _credentials(validated.credential_reference)
                output = {"connection_id": str(validated.id), "status": "CREDENTIAL_AVAILABLE"}
            elif args.command == "estimate":
                output = {
                    "estimated_cost": str(
                        estimate_cost(
                            args.limit, task_cost=args.task_cost, item_cost=args.item_cost
                        )
                    ),
                    "currency": "USD",
                    "assumption": "PLACEHOLDER_REVIEWED_2026-08-30",
                    "live_request_performed": False,
                }
            elif args.command == "inspect":
                rows = session.scalars(
                    select(ExternalSearchObservation)
                    .order_by(ExternalSearchObservation.observed_at.desc())
                    .limit(args.limit)
                ).all()
                output = [
                    {
                        "id": str(row.id),
                        "type": row.observation_type,
                        "domain": row.target_domain,
                        "observed_at": row.observed_at.isoformat(),
                        "items": row.items_returned,
                    }
                    for row in rows
                ]
            else:
                connection = session.get(DataSourceConnection, args.connection)
                site = session.get(Site, args.site)
                if not connection or not site:
                    raise ValueError("connection or site not found")
                kind = args.kind or (
                    "competitors" if args.command == "competitors" else "ranked_keywords"
                )
                request = SearchRequest(
                    observation_type=kind,
                    target_domain=args.domain,
                    location_code=args.location_code,
                    location_name=args.location_name,
                    country_code=args.country,
                    language_code=args.language,
                    device=args.device,
                    limit=args.limit,
                )
                estimated = estimate_cost(args.limit)
                if args.dry_run:
                    output = {
                        "kind": kind,
                        "domain": args.domain,
                        "limit": args.limit,
                        "estimated_cost": str(estimated),
                        "live_request_performed": False,
                    }
                else:
                    login, password = _credentials(connection.credential_reference)
                    run_row = ExternalSearchCollector(
                        session, DataForSEOExternalSearchProvider(login, password)
                    ).sync(connection.id, site.id, request, estimated_cost=estimated)
                    output = {
                        "run_id": str(run_row.id),
                        "status": run_row.status.value,
                        **({"error": run_row.error_summary} if run_row.error_summary else {}),
                    }
        print(json.dumps(output))
        return 0
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error)}))
        return 2


def main() -> None:
    raise SystemExit(run())
