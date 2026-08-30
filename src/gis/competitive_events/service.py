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
REPROCESS_METADATA_KEY = "reprocessing"


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.normalize(), "f")


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
        return self._record(
            tenant_id, site_id, candidate, event_identity(tenant_id, site_id, candidate)
        )

    def _record(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        candidate: EventCandidate,
        identity: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> CompetitiveEvent:
        site = self.session.scalar(
            select(Site).where(Site.id == site_id, Site.tenant_id == tenant_id)
        )
        if not site:
            raise ValueError("site does not belong to tenant")
        if not candidate.evidence:
            raise ValueError("competitive events require evidence")
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
            metadata_json=metadata if metadata is not None else candidate.metadata,
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

    def reprocess(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        domains: Iterable[CompetitiveEventDomain],
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        """Recompute a bounded window while retaining correction history."""
        policy = self._validate_window(tenant_id, site_id, start, end)
        from gis.competitive_events.adapters import ADAPTERS, candidates_for

        selected = list(domains)
        recomputed_domains = [item for item in selected if item in ADAPTERS]
        candidates = candidates_for(
            self.session,
            tenant_id,
            site_id,
            recomputed_domains,
            start,
            end,
            policy.thresholds_json,
        )
        history = self.session.scalars(
            select(CompetitiveEvent)
            .where(
                CompetitiveEvent.tenant_id == tenant_id,
                CompetitiveEvent.site_id == site_id,
                CompetitiveEvent.event_domain.in_(recomputed_domains),
                CompetitiveEvent.event_time >= start,
                CompetitiveEvent.event_time <= end,
            )
            .order_by(CompetitiveEvent.created_at, CompetitiveEvent.id)
        ).all()
        history_by_lineage: dict[str, list[CompetitiveEvent]] = {}
        for item in history:
            history_by_lineage.setdefault(self._lineage_identity(item), []).append(item)
        active_by_lineage = {
            lineage: next(
                (item for item in reversed(items) if item.status == CompetitiveEventStatus.ACTIVE),
                None,
            )
            for lineage, items in history_by_lineage.items()
        }
        seen: set[str] = set()
        created = 0
        superseded = 0

        for candidate in candidates:
            lineage = event_identity(tenant_id, site_id, candidate)
            seen.add(lineage)
            current = active_by_lineage.get(lineage)
            fingerprint = self._candidate_fingerprint(candidate)
            if current is not None and self._event_fingerprint(current) == fingerprint:
                continue

            predecessor = current
            if predecessor is None and history_by_lineage.get(lineage):
                predecessor = history_by_lineage[lineage][-1]

            if predecessor is None:
                replacement = self.record(tenant_id, site_id, candidate)
                created += 1
                continue

            correction_identity = hashlib.sha256(
                json.dumps(
                    [
                        "competitive-event-correction-v1",
                        lineage,
                        predecessor.identity_hash,
                        fingerprint,
                    ],
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            correction_metadata = dict(candidate.metadata)
            correction_metadata[REPROCESS_METADATA_KEY] = {
                "lineage_identity": lineage,
                "outcome_fingerprint": fingerprint,
            }
            replacement = self._record(
                tenant_id,
                site_id,
                candidate,
                correction_identity,
                metadata=correction_metadata,
            )
            if current is None:
                self.relate(
                    tenant_id,
                    site_id,
                    replacement.id,
                    predecessor.id,
                    EventRelationshipType.SUPERSEDES,
                )
                created += 1
                continue
            if replacement.id != current.id:
                self.supersede(current, replacement, "bounded deterministic reprocessing")
                superseded += 1
                created += 1

        retracted = 0
        for lineage, event in active_by_lineage.items():
            if event is not None and lineage not in seen:
                self.retract(event, "not reproduced by bounded deterministic reprocessing")
                retracted += 1

        return {
            "tenant_id": str(tenant_id),
            "site_id": str(site_id),
            "domains": [item.value for item in selected],
            "start": start.isoformat(),
            "end": end.isoformat(),
            "events_created": created,
            "events_superseded": superseded,
            "events_retracted": retracted,
            "provider_cost": "0",
        }

    def _lineage_identity(self, event: CompetitiveEvent) -> str:
        reprocessing = (event.metadata_json or {}).get(REPROCESS_METADATA_KEY, {})
        return str(reprocessing.get("lineage_identity", event.identity_hash))

    def _candidate_fingerprint(
        self,
        candidate: EventCandidate,
        *,
        persisted_rights: tuple[uuid.UUID | None, str | None, Any] | None = None,
    ) -> str:
        rights_ids = {item.rights_policy_id for item in candidate.evidence if item.rights_policy_id}
        rights_versions = {
            item.rights_policy_version for item in candidate.evidence if item.rights_policy_version
        }
        if persisted_rights is None:
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
            rights_status = aggregate_evaluations(
                PermittedUse.DERIVATIVE_CREATION, evaluations
            ).status
            rights_policy_id = next(iter(rights_ids)) if len(rights_ids) == 1 else None
            rights_policy_version = (
                next(iter(rights_versions)) if len(rights_versions) == 1 else None
            )
        else:
            rights_policy_id, rights_policy_version, rights_status = persisted_rights
        payload = {
            "subject": [
                candidate.subject_type.value,
                str(candidate.subject_id) if candidate.subject_id else None,
                candidate.subject_key,
                candidate.subject_domain,
                candidate.subject_url,
            ],
            "event": [
                candidate.event_domain.value,
                candidate.event_type.value,
                candidate.event_subtype,
                candidate.event_time.isoformat(),
                candidate.semantic_class.value,
                _decimal_text(
                    min(
                        [
                            candidate.confidence,
                            *(item.confidence for item in candidate.evidence),
                        ]
                    )
                ),
                _decimal_text(candidate.magnitude),
                candidate.magnitude_unit,
                candidate.synthesis_method,
                METHOD_VERSION,
            ],
            "rights": [
                str(rights_policy_id) if rights_policy_id else None,
                rights_policy_version,
                rights_status.value,
            ],
            "evidence": sorted(
                (
                    {
                        "source_asset": item.source_asset,
                        "source_record_id": item.source_record_id,
                        "observation_time": item.observation_time.isoformat(),
                        "role": item.role.value,
                        "semantic_class": item.semantic_class.value,
                        "confidence": _decimal_text(item.confidence),
                        "data_source_connection_id": str(item.data_source_connection_id)
                        if item.data_source_connection_id
                        else None,
                        "ingestion_run_id": str(item.ingestion_run_id)
                        if item.ingestion_run_id
                        else None,
                        "rights_policy_id": str(item.rights_policy_id)
                        if item.rights_policy_id
                        else None,
                        "rights_policy_version": item.rights_policy_version,
                        "metadata": item.metadata,
                    }
                    for item in candidate.evidence
                ),
                key=lambda item: json.dumps(item, sort_keys=True, default=str),
            ),
            "metadata": candidate.metadata,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()

    def _event_fingerprint(self, event: CompetitiveEvent) -> str:
        reprocessing = (event.metadata_json or {}).get(REPROCESS_METADATA_KEY, {})
        stored = reprocessing.get("outcome_fingerprint")
        if stored:
            return str(stored)
        evidence = self.session.scalars(
            select(CompetitiveEventEvidence).where(
                CompetitiveEventEvidence.competitive_event_id == event.id
            )
        ).all()
        candidate = EventCandidate(
            subject_type=event.subject_type,
            subject_id=event.subject_id,
            subject_key=event.subject_key,
            subject_domain=event.subject_domain,
            subject_url=event.subject_url,
            event_domain=event.event_domain,
            event_type=event.event_type,
            event_subtype=event.event_subtype,
            event_time=event.event_time,
            semantic_class=event.semantic_class,
            confidence=event.confidence,
            magnitude=event.magnitude,
            magnitude_unit=event.magnitude_unit,
            synthesis_method=event.synthesis_method,
            metadata={
                key: value
                for key, value in (event.metadata_json or {}).items()
                if key != REPROCESS_METADATA_KEY
            },
            evidence=tuple(
                EvidenceRef(
                    source_asset=item.source_asset,
                    source_record_id=item.source_record_id,
                    observation_time=item.observation_time,
                    role=item.evidence_role,
                    semantic_class=item.semantic_class,
                    confidence=item.confidence,
                    data_source_connection_id=item.data_source_connection_id,
                    ingestion_run_id=item.ingestion_run_id,
                    rights_policy_id=item.rights_policy_id,
                    rights_policy_version=item.rights_policy_version,
                    metadata=item.metadata_json,
                )
                for item in evidence
            ),
        )
        return self._candidate_fingerprint(
            candidate,
            persisted_rights=(
                event.rights_policy_id,
                event.rights_policy_version,
                event.effective_rights_status,
            ),
        )

    def _validate_window(
        self, tenant_id: uuid.UUID, site_id: uuid.UUID, start: datetime, end: datetime
    ) -> CompetitiveEventPolicy:
        if start >= end:
            raise ValueError("start must precede end")
        policy = self.ensure_policy(tenant_id, site_id)
        maximum = int(policy.thresholds_json.get("maximum_window_days", 366))
        if (end - start).days > maximum:
            raise ValueError(f"synthesis window cannot exceed {maximum} days")
        return policy

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
        policy = self._validate_window(tenant_id, site_id, start, end)
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
