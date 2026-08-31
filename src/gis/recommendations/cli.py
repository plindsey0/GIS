from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Sequence
from datetime import date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import select

from gis.db import session_factory
from gis.models import (
    Opportunity,
    Recommendation,
    RecommendationCandidate,
    RecommendationReviewDecision,
)
from gis.recommendations.provider import FixtureRecommendationProvider
from gis.recommendations.service import RecommendationService


def default(value: Any) -> Any:
    if isinstance(value, (uuid.UUID, datetime, date)):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-recommendations")
    commands = root.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--opportunity-id", type=uuid.UUID, required=True)
    generate.add_argument("--dry-run", action="store_true")
    generate.add_argument("--force", action="store_true")
    generate_all = commands.add_parser("generate-all")
    generate_all.add_argument("--tenant-id", type=uuid.UUID, required=True)
    generate_all.add_argument("--site-id", type=uuid.UUID, required=True)
    generate_all.add_argument("--dry-run", action="store_true")
    listing = commands.add_parser("list")
    listing.add_argument("--tenant-id", type=uuid.UUID, required=True)
    listing.add_argument("--site-id", type=uuid.UUID, required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--recommendation-id", type=uuid.UUID, required=True)
    review = commands.add_parser("review")
    review.add_argument("--recommendation-id", type=uuid.UUID, required=True)
    review.add_argument("--decision", choices=[item.value for item in RecommendationReviewDecision], required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--candidate-id", type=uuid.UUID, action="append", default=[])
    review.add_argument("--reason")
    return root


def run(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = parser().parse_args(argv)
    provider = FixtureRecommendationProvider()
    with session_factory()() as session:
        service = RecommendationService(session, provider)
        if args.command == "generate":
            result = service.generate(args.opportunity_id, dry_run=args.dry_run, force=args.force)
            session.rollback() if args.dry_run else session.commit()
            return result
        if args.command == "generate-all":
            ids = list(session.scalars(select(Opportunity.id).where(Opportunity.tenant_id == args.tenant_id, Opportunity.site_id == args.site_id)))
            results = [service.generate(item, dry_run=args.dry_run) for item in ids]
            session.rollback() if args.dry_run else session.commit()
            return {"opportunity_count": len(ids), "results": results, "ai_calls": provider.calls}
        if args.command == "list":
            rows = service.list(args.tenant_id, args.site_id)
            return {"recommendations": [{"id": row.id, "opportunity_id": row.opportunity_id, "status": row.status, "summary": row.summary} for row in rows]}
        if args.command == "inspect":
            row = session.get(Recommendation, args.recommendation_id)
            if not row:
                raise ValueError("recommendation not found")
            candidates = list(session.scalars(select(RecommendationCandidate).where(RecommendationCandidate.recommendation_id == row.id).order_by(RecommendationCandidate.rank)))
            return {"id": row.id, "opportunity_id": row.opportunity_id, "status": row.status, "summary": row.summary, "candidates": [{"id": item.id, "rank": item.rank, "target_metric": item.target_metric_key, "rationale": item.rationale, "accepted_intervention_id": item.accepted_intervention_id} for item in candidates]}
        row = service.review(args.recommendation_id, RecommendationReviewDecision(args.decision), args.reviewer, args.candidate_id, reason=args.reason)
        session.commit()
        return {"id": row.id, "status": row.status, "human_review_recorded": True, "intervention_approval_granted": False}


def main() -> None:
    try:
        print(json.dumps(run(), default=default, sort_keys=True))
    except Exception as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
