from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.competitive_events.policy import DEFAULT_THRESHOLDS, POLICY_NAME, POLICY_VERSION
from gis.models import (
    CompetitiveEvent,
    CompetitiveEventDomain,
    CompetitiveEventEvidence,
    CompetitiveEventPolicy,
    CompetitiveEventRelationship,
    CompetitiveEventStatus,
    CompetitiveEventType,
    CompetitiveSubjectType,
    DataRightsPolicy,
    EventRelationshipType,
    EventSemanticClass,
    EvidenceRole,
    PermittedUse,
    Site,
)

METHOD_VERSION = "1.0.0"
PUBLIC_NAMESPACE = uuid.UUID("f77a7661-a5c4-4e37-bbac-056504b7ee96")


@dataclass(frozen=True)
class EvidenceRef:
    source_asset: str
    source_record_id: str
    observation_time: datetime
    role: EvidenceRole
    semantic_class: EventSemanticClass
    confidence: Decimal
    data_source_connection_id: uuid.UUID | None = None
    ingestion_run_id: uuid.UUID | None = None
    rights_policy_id: uuid.UUID | None = None
    rights_policy_version: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventCandidate:
    subject_type: CompetitiveSubjectType
    subject_key: str
    event_domain: CompetitiveEventDomain
    event_type: CompetitiveEventType
    event_time: datetime
    evidence: tuple[EvidenceRef, ...]
    semantic_class: EventSemanticClass = EventSemanticClass.GIS_DERIVED
    confidence: Decimal = Decimal("1")
    subject_id: uuid.UUID | None = None
    subject_domain: str | None = None
    subject_url: str | None = None
    event_subtype: str | None = None
    magnitude: Decimal | None = None
    magnitude_unit: str | None = None
    synthesis_method: str = "deterministic_comparison"
    metadata: dict[str, Any] = field(default_factory=dict)


def event_identity(tenant_id: uuid.UUID, site_id: uuid.UUID, candidate: EventCandidate) -> str:
    evidence = sorted(
        f"{item.source_asset}:{item.source_record_id}:{item.role.value}"
        for item in candidate.evidence
    )
    payload = [
        str(tenant_id),
        str(site_id),
        candidate.subject_type.value,
        candidate.subject_key,
        candidate.event_type.value,
        candidate.event_time.isoformat(),
        candidate.synthesis_method,
        METHOD_VERSION,
        *evidence,
    ]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


class SynthesisService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_policy(self, tenant_id: uuid.UUID, site_id: uuid.UUID) -> CompetitiveEventPolicy:
        policy = self.session.scalar(
            select(CompetitiveEventPolicy).where(
                CompetitiveEventPolicy.tenant_id == tenant_id,
                CompetitiveEventPolicy.site_id == site_id,
                CompetitiveEventPolicy.name == POLICY_NAME,
                CompetitiveEventPolicy.policy_version == POLICY_VERSION,
            )
        )
        if policy:
            return policy
        policy = CompetitiveEventPolicy(
            tenant_id=tenant_id,
            site_id=site_id,
            name=POLICY_NAME,
            policy_version=POLICY_VERSION,
            thresholds_json=DEFAULT_THRESHOLDS,
        )
        self.session.add(policy)
        self.session.flush()
        return policy

    def record(
        self, tenant_id: uuid.UUID, site_id: uuid.UUID, candidate: EventCandidate
    ) -> CompetitiveEvent:
        site = self.session.scalar(
            select(Site).where(Site.id == site_id, Site.tenant_id == tenant_id)
        )
        if not site:
            raise ValueError("site does not belong to tenant")
        if not candidate.evidence:
            raise ValueError("competitive events require evidence")
        identity = event_identity(tenant_id, site_id, candidate)
        existing = self.session.scalar(
            select(CompetitiveEvent).where(
                CompetitiveEvent.tenant_id == tenant_id,
                CompetitiveEvent.site_id == site_id,
                CompetitiveEvent.identity_hash == identity,
            )
        )
        if existing:
            return existing
        policy = self.ensure_policy(tenant_id, site_id)
        rights_ids = {item.rights_policy_id for item in candidate.evidence if item.rights_policy_id}
        rights_versions = {
            item.rights_policy_version for item in candidate.evidence if item.rights_policy_version
        }
        from gis.provenance.service import aggregate_evaluations, evaluate_policy_use

        evaluations = [
            evaluate_policy_use(
                self.session,
                self.session.get(DataRightsPolicy, item.rights_policy_id)
                if item.rights_policy_id
                else None,
                PermittedUse.DERIVATIVE_CREATION,
            )
            for item in candidate.evidence
        ]
        # DENIED dominates UNKNOWN; UNKNOWN dominates ALLOWED. This is intentionally fail closed.
        effective_rights = aggregate_evaluations(
            PermittedUse.DERIVATIVE_CREATION, evaluations
        ).status
        event = CompetitiveEvent(
            public_id=uuid.uuid5(PUBLIC_NAMESPACE, identity),
            tenant_id=tenant_id,
            organization_id=site.organization_id,
            site_id=site_id,
            subject_type=candidate.subject_type,
            subject_id=candidate.subject_id,
            subject_key=candidate.subject_key,
            subject_domain=candidate.subject_domain,
            subject_url=candidate.subject_url,
            event_domain=candidate.event_domain,
            event_type=candidate.event_type,
            event_subtype=candidate.event_subtype,
            event_time=candidate.event_time,
            first_observed_at=min(item.observation_time for item in candidate.evidence),
            detected_at=max(item.observation_time for item in candidate.evidence),
            semantic_class=candidate.semantic_class,
            confidence=min(
                [candidate.confidence, *(item.confidence for item in candidate.evidence)]
            ),
            magnitude=candidate.magnitude,
            magnitude_unit=candidate.magnitude_unit,
            status=CompetitiveEventStatus.ACTIVE,
            synthesis_method=candidate.synthesis_method,
            synthesis_method_version=METHOD_VERSION,
            policy_id=policy.id,
            policy_version=policy.policy_version,
            rights_policy_id=next(iter(rights_ids)) if len(rights_ids) == 1 else None,
            rights_policy_version=next(iter(rights_versions))
            if len(rights_versions) == 1
            else None,
            effective_rights_status=effective_rights,
            identity_hash=identity,
            provider_cost=Decimal("0"),
            metadata_json=candidate.metadata,
        )
        self.session.add(event)
        self.session.flush()
        for item in candidate.evidence:
            self.session.add(
                CompetitiveEventEvidence(
                    tenant_id=tenant_id,
                    site_id=site_id,
                    competitive_event_id=event.id,
                    source_asset=item.source_asset,
                    source_record_id=item.source_record_id,
                    observation_time=item.observation_time,
                    evidence_role=item.role,
                    semantic_class=item.semantic_class,
                    confidence=item.confidence,
                    data_source_connection_id=item.data_source_connection_id,
                    ingestion_run_id=item.ingestion_run_id,
                    rights_policy_id=item.rights_policy_id,
                    rights_policy_version=item.rights_policy_version,
                    metadata_json=item.metadata,
                )
            )
        self.session.flush()
        return event

    def relate(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        from_event_id: uuid.UUID,
        to_event_id: uuid.UUID,
        relationship_type: EventRelationshipType,
    ) -> CompetitiveEventRelationship:
        if from_event_id == to_event_id:
            raise ValueError("an event cannot relate to itself")
        events = self.session.scalars(
            select(CompetitiveEvent).where(
                CompetitiveEvent.tenant_id == tenant_id,
                CompetitiveEvent.site_id == site_id,
                CompetitiveEvent.id.in_([from_event_id, to_event_id]),
            )
        ).all()
        if len(events) != 2:
            raise ValueError("both events must belong to the tenant and site")
        existing = self.session.scalar(
            select(CompetitiveEventRelationship).where(
                CompetitiveEventRelationship.from_event_id == from_event_id,
                CompetitiveEventRelationship.to_event_id == to_event_id,
                CompetitiveEventRelationship.relationship_type == relationship_type,
            )
        )
        if existing:
            return existing
        relationship = CompetitiveEventRelationship(
            tenant_id=tenant_id,
            site_id=site_id,
            from_event_id=from_event_id,
            to_event_id=to_event_id,
            relationship_type=relationship_type,
        )
        self.session.add(relationship)
        self.session.flush()
        return relationship

    def supersede(
        self, original: CompetitiveEvent, replacement: CompetitiveEvent, reason: str
    ) -> None:
        if (original.tenant_id, original.site_id) != (replacement.tenant_id, replacement.site_id):
            raise ValueError("cross-tenant or cross-site supersession is forbidden")
        original.status = CompetitiveEventStatus.SUPERSEDED
        original.replaced_by_event_id = replacement.id
        original.correction_reason = reason
        self.relate(
            original.tenant_id,
            original.site_id,
            replacement.id,
            original.id,
            EventRelationshipType.SUPERSEDES,
        )

    def retract(self, event: CompetitiveEvent, reason: str) -> None:
        event.status = CompetitiveEventStatus.RETRACTED
        event.correction_reason = reason

    def synthesize(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        domains: Iterable[CompetitiveEventDomain],
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        if start >= end:
            raise ValueError("start must precede end")
        policy = self.ensure_policy(tenant_id, site_id)
        maximum = int(policy.thresholds_json.get("maximum_window_days", 366))
        if (end - start).days > maximum:
            raise ValueError(f"synthesis window cannot exceed {maximum} days")
        from gis.competitive_events.adapters import candidates_for

        selected = list(domains)
        candidates = candidates_for(
            self.session,
            tenant_id,
            site_id,
            selected,
            start,
            end,
            policy.thresholds_json,
        )
        created: list[CompetitiveEvent] = []
        existing_ids = set(
            self.session.scalars(
                select(CompetitiveEvent.id).where(
                    CompetitiveEvent.tenant_id == tenant_id,
                    CompetitiveEvent.site_id == site_id,
                )
            ).all()
        )
        for candidate in candidates:
            event = self.record(tenant_id, site_id, candidate)
            if event.id not in existing_ids:
                created.append(event)
                existing_ids.add(event.id)
        cross_created = self._cross_source(tenant_id, site_id, start, end, policy)
        return {
            "tenant_id": str(tenant_id),
            "site_id": str(site_id),
            "domains": [item.value for item in selected],
            "start": start.isoformat(),
            "end": end.isoformat(),
            "events_created": len(created) + cross_created,
            "provider_cost": "0",
        }

    def _cross_source(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        start: datetime,
        end: datetime,
        policy: CompetitiveEventPolicy,
    ) -> int:
        from datetime import timedelta

        window = timedelta(days=int(policy.thresholds_json.get("cross_source_window_days", 14)))
        events = self.session.scalars(
            select(CompetitiveEvent).where(
                CompetitiveEvent.tenant_id == tenant_id,
                CompetitiveEvent.site_id == site_id,
                CompetitiveEvent.event_time >= start - window,
                CompetitiveEvent.event_time <= end,
                CompetitiveEvent.event_type.in_(
                    [
                        CompetitiveEventType.PAGE_FIRST_OBSERVED,
                        CompetitiveEventType.SERP_RANK_ENTERED,
                    ]
                ),
                CompetitiveEvent.subject_url.is_not(None),
            )
        ).all()
        by_url: dict[str, dict[CompetitiveEventType, list[CompetitiveEvent]]] = {}
        for event in events:
            assert event.subject_url is not None
            by_url.setdefault(event.subject_url, {}).setdefault(event.event_type, []).append(event)
        created = 0
        for url, types in by_url.items():
            for content in types.get(CompetitiveEventType.PAGE_FIRST_OBSERVED, []):
                for serp in types.get(CompetitiveEventType.SERP_RANK_ENTERED, []):
                    if abs(content.event_time - serp.event_time) > window:
                        continue
                    refs = tuple(
                        EvidenceRef(
                            "gis_core.competitive_event",
                            str(item.id),
                            item.event_time,
                            EvidenceRole.SUPPORTING,
                            item.semantic_class,
                            item.confidence,
                            rights_policy_id=item.rights_policy_id,
                            rights_policy_version=item.rights_policy_version,
                        )
                        for item in (content, serp)
                    )
                    candidate = EventCandidate(
                        CompetitiveSubjectType.PAGE,
                        url,
                        CompetitiveEventDomain.CROSS_SOURCE,
                        CompetitiveEventType.COMPETITOR_PAGE_EMERGENCE,
                        max(content.event_time, serp.event_time),
                        refs,
                        EventSemanticClass.GIS_DERIVED,
                        min(content.confidence, serp.confidence),
                        subject_domain=content.subject_domain or serp.subject_domain,
                        subject_url=url,
                        synthesis_method="cross_source_association",
                    )
                    identity = event_identity(tenant_id, site_id, candidate)
                    existed = self.session.scalar(
                        select(CompetitiveEvent.id).where(
                            CompetitiveEvent.tenant_id == tenant_id,
                            CompetitiveEvent.site_id == site_id,
                            CompetitiveEvent.identity_hash == identity,
                        )
                    )
                    cross = self.record(tenant_id, site_id, candidate)
                    if not existed:
                        created += 1
                    self.relate(
                        tenant_id,
                        site_id,
                        content.id,
                        cross.id,
                        EventRelationshipType.CONSTITUENT_OF,
                    )
                    self.relate(
                        tenant_id,
                        site_id,
                        serp.id,
                        cross.id,
                        EventRelationshipType.CONSTITUENT_OF,
                    )
        return created
