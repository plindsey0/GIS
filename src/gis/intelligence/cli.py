from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

from sqlalchemy import select

from gis.db import session_factory
from gis.intelligence.config import provider_from_environment
from gis.intelligence.provider import ReplayLLMProvider
from gis.intelligence.replay import replay_responses
from gis.intelligence.service import EvidencePacketService, GovernedIntelligenceService
from gis.models import ExperimentProposal, Site, Tenant


def _scope(session: Any, tenant_slug: str, site_slug: str) -> tuple[Tenant, Site]:
    tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    site = session.scalar(select(Site).where(Site.slug == site_slug))
    if not tenant or not site or site.tenant_id != tenant.id:
        raise ValueError("tenant/site scope not found")
    return tenant, site


def main() -> None:
    parser = argparse.ArgumentParser(prog="gis-intelligence")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("packet", "demo"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--tenant", required=True)
        cmd.add_argument("--site", required=True)
        cmd.add_argument("--evidence-id", action="append", type=uuid.UUID)
        cmd.add_argument("--entity-id", type=uuid.UUID)
        cmd.add_argument("--limit", type=int, default=10)
        if name == "demo":
            cmd.add_argument("--reviewer", required=True,
                             help="Human actor accepting/selecting the fixture-provider artifacts")
    live = sub.add_parser("live-opportunities")
    live.add_argument("--tenant", required=True)
    live.add_argument("--site", required=True)
    live_scope = live.add_mutually_exclusive_group(required=True)
    live_scope.add_argument("--evidence-id", action="append", type=uuid.UUID)
    live_scope.add_argument("--entity-id", type=uuid.UUID)
    live.add_argument("--limit", type=int, default=10)
    live.add_argument(
        "--confirm-paid-provider-call",
        action="store_true",
        help="Required explicit authorization for this command to make one live provider call",
    )
    regenerate = sub.add_parser("live-regenerate-proposal")
    regenerate.add_argument("--tenant", required=True)
    regenerate.add_argument("--site", required=True)
    regenerate.add_argument("--proposal-id", required=True, type=uuid.UUID)
    regenerate.add_argument("--confirm-paid-provider-call", action="store_true")
    args = parser.parse_args()
    with session_factory()() as session:
        tenant, site = _scope(session, args.tenant, args.site)
        if args.command == "live-regenerate-proposal":
            if not args.confirm_paid_provider_call:
                raise ValueError(
                    "live-regenerate-proposal requires --confirm-paid-provider-call; no call was made"
                )
            original = session.get(ExperimentProposal, args.proposal_id)
            if not original or original.tenant_id != tenant.id or original.site_id != site.id:
                raise ValueError("proposal not found in permitted tenant/site scope")
            provider = provider_from_environment(allow_live=True)
            replacement = GovernedIntelligenceService(
                session, provider
            ).generate_experiment_proposal(
                original.recommendation_id, supersedes_proposal_id=original.id
            )
            session.commit()
            print(json.dumps({"id": str(replacement.id), "provider": provider.key,
                              "supersedes_proposal_id": str(original.id),
                              "human_review_required": True}, indent=2))
            return
        if getattr(args, "entity_id", None) and getattr(args, "evidence_id", None):
            raise ValueError("Choose either --entity-id or --evidence-id, not both.")
        packet_service = EvidencePacketService(session)
        packet = packet_service.build_for_entity(
            tenant.id, site.id, args.entity_id, limit=args.limit
        ) if getattr(args, "entity_id", None) else packet_service.build(
            tenant.id, site.id, evidence_ids=args.evidence_id, limit=args.limit
        )
        if args.command == "packet":
            print(packet.model_dump_json(indent=2))
            return
        if args.command == "live-opportunities":
            if not args.confirm_paid_provider_call:
                raise ValueError(
                    "live-opportunities requires --confirm-paid-provider-call; no call was made"
                )
            provider = provider_from_environment(allow_live=True)
            opportunities = GovernedIntelligenceService(session, provider).generate_opportunities(
                packet
            )
            session.commit()
            print(json.dumps({
                "provider": provider.key,
                "model": provider.model_identifier,
                "candidate_opportunities": [
                    {"id": str(item.id), "title": item.title, "status": item.status.value}
                    for item in opportunities
                ],
                "human_review_required": True,
            }, indent=2))
            return
        evidence_id = packet.evidence[0].evidence_id
        subject = packet.evidence[0].subject
        provider = ReplayLLMProvider(replay_responses(evidence_id, target=subject))
        service = GovernedIntelligenceService(session, provider)
        opportunity = service.generate_opportunities(packet)[0]
        service.review_opportunity(opportunity.id, "ACCEPTED", args.reviewer,
                                   "Explicit provider-free demonstration acceptance")
        provider.responses.update(
            replay_responses(evidence_id, opportunity_id=opportunity.id, target=subject)
        )
        recommendation = service.generate_recommendations([opportunity.id])[0]
        service.select_recommendation(recommendation.id, args.reviewer,
                                      "Explicit provider-free demonstration selection")
        provider.responses.update(replay_responses(evidence_id, recommendation_id=recommendation.id,
                                             opportunity_id=opportunity.id,
                                             target=packet.evidence[0].subject))
        proposal = service.generate_experiment_proposal(recommendation.id)
        session.commit()
        print(json.dumps({"provider_calls": len(provider.calls), "paid_provider_calls": 0,
            "evidence_packet": packet.model_dump(mode="json"),
            "human_decisions": {"opportunity": "ACCEPTED", "recommendation": "SELECTED", "reviewer": args.reviewer},
            "candidate_opportunity": {"id": str(opportunity.id), "title": opportunity.title},
            "recommendation": {"id": str(recommendation.id), "summary": recommendation.summary},
            "experiment_proposal": {"id": str(proposal.id), "title": proposal.title,
                "target": proposal.target_url_or_resource, "hypothesis": proposal.hypothesis,
                "treatment": proposal.treatment_description, "primary_metric": proposal.primary_metric,
                "guardrails": proposal.guardrail_metrics_json, "decision_rule": proposal.decision_rule},
            "lineage": service.lineage(proposal.id)}, default=str, indent=2))


if __name__ == "__main__":
    main()
