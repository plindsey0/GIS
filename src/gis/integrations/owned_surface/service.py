from __future__ import annotations

import hashlib
import ipaddress
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.integrations.content_intelligence.extraction import (
    ExtractedPage,
    extract_page,
    normalize_url,
)
from gis.integrations.content_intelligence.retrieval import ContentRetriever, RetrievalResult
from gis.integrations.content_intelligence.service import CompetitiveContentCollector
from gis.models import (
    AnalyticalEntity,
    CollectionTarget,
    CollectionTargetStatus,
    CollectionTargetType,
    CompetitiveContentObservation,
    CorroborationState,
    DataRightsPolicy,
    DemandEvidenceStrength,
    EvidenceCompatibility,
    EvidenceContract,
    EvidenceGap,
    EvidencePackage,
    EvidencePackageItem,
    EvidenceQualityDimension,
    EvidenceQualityRun,
    IngestionRun,
    IngestionStatus,
    OwnedSurfaceObservationDetail,
    PermittedUse,
    QualityDimensionState,
    QualityDimensionType,
    ResolutionStrength,
    RightsStatus,
    RightsUsability,
    Site,
    SourceIndependenceState,
)
from gis.provenance.service import evaluate_policy_use

METHOD_VERSION = "OWNED_SURFACE_OBSERVATION_V1"
MAX_VISIBLE_TEXT = 12_000
MAX_CONTROLS = 100
MAX_IMAGES = 100
MAX_INSTRUMENTATION = 50


class OwnedSurfaceValidationError(ValueError):
    pass


class _CapturingRetriever:
    def __init__(self, delegate: ContentRetriever, allowed_host: str) -> None:
        self.delegate = delegate
        self.allowed_host = allowed_host
        self.result: RetrievalResult | None = None

    def retrieve(self, url: str) -> RetrievalResult:
        result = self.delegate.retrieve(url)
        resolved_host = normalize_url(result.resolved_url)[1]
        if resolved_host != self.allowed_host:
            raise OwnedSurfaceValidationError(
                "redirect left the governed owned-site boundary"
            )
        self.result = result
        return result


def validate_owned_url(site: Site, value: str) -> str:
    supplied = urlsplit(value.strip())
    if supplied.username or supplied.password:
        raise OwnedSurfaceValidationError("URL credentials are not allowed")
    normalized, hostname, _ = normalize_url(value)
    governed_host = normalize_url(site.canonical_url)[1]
    if hostname != governed_host:
        raise OwnedSurfaceValidationError("URL is outside the governed site hostname")
    parsed = urlsplit(normalized)
    try:
        address = ipaddress.ip_address(parsed.hostname or "")
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise OwnedSurfaceValidationError("private, local, and reserved targets are prohibited")
    return normalized


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _indexability(page: ExtractedPage, observation: CompetitiveContentObservation) -> str:
    directives = set(page.robots)
    header_directives = {
        item.strip().casefold()
        for item in str(observation.retrieval_metadata.get("x_robots_tag") or "").split(",")
        if item.strip()
    }
    if "noindex" in directives | header_directives:
        return "OBSERVED_NOINDEX"
    if observation.http_status and observation.http_status >= 400:
        return "HTTP_NOT_INDEXABLE"
    return "NO_BLOCKING_DIRECTIVE_OBSERVED"


def _change(
    previous: OwnedSurfaceObservationDetail | None,
    fingerprints: dict[str, str],
    canonical: str,
    indexability: str,
) -> str:
    if not previous:
        return "FIRST_OBSERVATION"
    if previous.raw_response_fingerprint == fingerprints["raw"]:
        return "UNCHANGED"
    changes = []
    if previous.metadata_fingerprint != fingerprints["metadata"]:
        changes.append("METADATA")
    if previous.normalized_content_fingerprint != fingerprints["content"]:
        changes.append("CONTENT")
    if previous.structure_fingerprint != fingerprints["structure"]:
        changes.append("STRUCTURE")
    if (
        previous.canonical_assessment != canonical
        or previous.indexability_assessment != indexability
    ):
        changes.append("CANONICAL_INDEXABILITY")
    return "_AND_".join(changes) + "_CHANGED" if changes else "RAW_ONLY_CHANGED"


class OwnedSurfaceObservationService:
    """Orchestrates a single authorized owned URL; it never schedules or recursively crawls."""

    def __init__(self, session: Session, retriever: ContentRetriever) -> None:
        self.session = session
        self.retriever = retriever

    def collect(
        self,
        connection_id: uuid.UUID,
        site_id: uuid.UUID,
        collection_target_id: uuid.UUID,
        analytical_entity_id: uuid.UUID,
    ) -> IngestionRun:
        site = self.session.get(Site, site_id)
        target = self.session.get(CollectionTarget, collection_target_id)
        entity = self.session.get(AnalyticalEntity, analytical_entity_id)
        if not site or not target or target.tenant_id != site.tenant_id or target.site_id != site.id:
            raise OwnedSurfaceValidationError("collection target is outside site scope")
        if not entity or entity.tenant_id != site.tenant_id or entity.site_id != site.id:
            raise OwnedSurfaceValidationError("analytical entity is outside site scope")
        if target.target_type is not CollectionTargetType.URL:
            raise OwnedSurfaceValidationError("owned-surface collection requires a URL target")
        if target.status is not CollectionTargetStatus.ACTIVE:
            raise OwnedSurfaceValidationError("collection target is not in an applied active plan")
        requested_url = validate_owned_url(site, target.display_value)
        capturing = _CapturingRetriever(self.retriever, normalize_url(site.canonical_url)[1])
        run = CompetitiveContentCollector(self.session, capturing).collect(
            connection_id, site.id, requested_url
        )
        if run.status is not IngestionStatus.SUCCEEDED or not capturing.result:
            return run
        observation = self.session.scalar(select(CompetitiveContentObservation).where(
            CompetitiveContentObservation.ingestion_run_id == run.id
        ))
        if not observation:
            # Existing content collector records unchanged replay in the run without duplicating
            # immutable extracted facts. Preserve the run as the recollection audit.
            return run
        page = extract_page(capturing.result.body, observation.resolved_url or requested_url)
        detail = self._detail(observation, target, page)
        self.session.add(detail)
        self.session.flush()
        detail.evidence_package_id = self._package(detail, observation, entity).id
        self.session.commit()
        return run

    def _detail(
        self,
        observation: CompetitiveContentObservation,
        target: CollectionTarget,
        page: ExtractedPage,
    ) -> OwnedSurfaceObservationDetail:
        previous = self.session.scalar(
            select(OwnedSurfaceObservationDetail)
            .where(OwnedSurfaceObservationDetail.collection_target_id == target.id)
            .order_by(OwnedSurfaceObservationDetail.observed_at.desc())
            .limit(1)
        )
        headings = [(level, text) for level, text in page.headings]
        fingerprints = {
            "raw": observation.content_hash or _fingerprint(""),
            "content": _fingerprint(page.visible_text.casefold()),
            "structure": _fingerprint({
                "headings": headings,
                "controls": page.controls,
                "landmarks": page.landmarks,
                "schema": page.schema_types,
            }),
            "metadata": _fingerprint({
                "title": page.title,
                "description": page.meta_description,
                "canonical": page.canonical_url,
                "robots": sorted(set(page.robots)),
                "status": observation.http_status,
            }),
        }
        limitations = ["Static HTTP observation; page scripts were not executed."]
        if observation.truncated:
            limitations.append("Response exceeded the configured byte limit and was truncated.")
        if not page.canonical_url:
            limitations.append("No canonical link declaration was observed.")
        if not page.visible_text:
            limitations.append("No visible text was extracted.")
        limitations.extend([
            "Control presence does not establish calculator correctness.",
            "Accessibility-related attributes do not establish WCAG conformance.",
            "Instrumentation presence does not establish event delivery correctness.",
        ])
        usable_retrieval = bool(
            observation.http_status
            and 200 <= observation.http_status < 300
            and page.visible_text
        )
        quality = (
            "USABLE_LIMITED"
            if usable_retrieval and not observation.truncated
            else "PARTIAL"
        )
        canonical = (
            "NOT_DECLARED" if not page.canonical_url
            else "MATCHES_OBSERVED_URL"
            if normalize_url(page.canonical_url)[0] == observation.normalized_url
            else "DIFFERS_FROM_OBSERVED_URL"
        )
        indexability = _indexability(page, observation)
        return OwnedSurfaceObservationDetail(
            observation_id=observation.id,
            tenant_id=observation.tenant_id,
            site_id=observation.site_id,
            collection_target_id=target.id,
            previous_observation_id=previous.observation_id if previous else None,
            observed_at=observation.observed_at,
            method_version=METHOD_VERSION,
            retrieval_state=observation.retrieval_status,
            render_state="NOT_RENDERED_STATIC_HTTP",
            canonical_assessment=canonical,
            indexability_assessment=indexability,
            raw_response_fingerprint=fingerprints["raw"],
            normalized_content_fingerprint=fingerprints["content"],
            structure_fingerprint=fingerprints["structure"],
            metadata_fingerprint=fingerprints["metadata"],
            change_classification=_change(previous, fingerprints, canonical, indexability),
            visible_text_preview=page.visible_text[:MAX_VISIBLE_TEXT],
            controls_json=page.controls[:MAX_CONTROLS],
            images_json=page.images[:MAX_IMAGES],
            landmarks_json=dict(page.landmarks),
            instrumentation_json=page.instrumentation[:MAX_INSTRUMENTATION],
            quality_state=quality,
            limitations_json=limitations,
            reassessment_ready=usable_retrieval,
        )

    def _package(
        self,
        detail: OwnedSurfaceObservationDetail,
        observation: CompetitiveContentObservation,
        entity: AnalyticalEntity,
    ) -> EvidencePackage:
        contract = self.session.scalar(select(EvidenceContract).where(
            EvidenceContract.contract_key == "OWNED_SURFACE_CONTENT",
            EvidenceContract.contract_version == METHOD_VERSION,
        ))
        if not contract:
            contract = EvidenceContract(
                contract_key="OWNED_SURFACE_CONTENT",
                contract_version=METHOD_VERSION,
                description="Governed, bounded owned-surface retrieval and extraction facts.",
                requirements_json={
                    "owned_scope": True,
                    "retrieval_required": True,
                    "render_optional": True,
                    "does_not_assert_intent_or_quality": True,
                },
            )
            self.session.add(contract)
            self.session.flush()
        run = EvidenceQualityRun(
            tenant_id=observation.tenant_id,
            site_id=observation.site_id,
            method_version=METHOD_VERSION,
            assessed_at=datetime.now(timezone.utc),
            fingerprint=_fingerprint([observation.id, METHOD_VERSION]),
            input_count=1,
            package_count=1,
            metadata_json={"provider_calls": 0, "observation_id": str(observation.id)},
        )
        self.session.add(run)
        self.session.flush()
        policy = self.session.get(DataRightsPolicy, observation.rights_policy_id)
        rights_decision = evaluate_policy_use(
            self.session, policy, PermittedUse.DERIVATIVE_CREATION
        ).status
        rights = (
            RightsUsability.USABLE
            if rights_decision is RightsStatus.ALLOWED else RightsUsability.BLOCKED
            if rights_decision is RightsStatus.DENIED else RightsUsability.UNKNOWN
        )
        if rights is not RightsUsability.USABLE:
            detail.reassessment_ready = False
            detail.limitations_json = [
                *detail.limitations_json,
                "Rights do not authorize derivative evidence use.",
            ]
        package = EvidencePackage(
            quality_run_id=run.id,
            tenant_id=observation.tenant_id,
            site_id=observation.site_id,
            analytical_entity_id=entity.id,
            evidence_contract_id=contract.id,
            condition_key="TARGET_PAGE_CONTENT_OBSERVATION",
            classification="OWNED_SURFACE_OBSERVED",
            period_start=observation.observed_at.date(),
            period_end=observation.observed_at.date(),
            sufficiency=DemandEvidenceStrength.LIMITED,
            identity_resolution=ResolutionStrength.EXACT,
            source_independence=SourceIndependenceState.SAME_ROOT_SOURCE,
            corroboration=CorroborationState.SINGLE_SOURCE,
            rights_usability=rights,
            conflict_count=0,
            independent_source_count=1,
            limitations_json=detail.limitations_json,
            identity_hash=_fingerprint([observation.id, contract.id, entity.id]),
            method_version=METHOD_VERSION,
        )
        self.session.add(package)
        self.session.flush()
        dimensions = {
            QualityDimensionType.IDENTITY_RESOLUTION: QualityDimensionState.STRONG,
            QualityDimensionType.FRESHNESS: QualityDimensionState.SUPPORTED,
            QualityDimensionType.COMPLETENESS: (
                QualityDimensionState.LIMITED
                if detail.quality_state == "PARTIAL" else QualityDimensionState.SUPPORTED
            ),
            QualityDimensionType.PROVENANCE_COMPLETENESS: QualityDimensionState.SUPPORTED,
            QualityDimensionType.METHOD_COMPATIBILITY: QualityDimensionState.SUPPORTED,
            QualityDimensionType.SCOPE_COMPATIBILITY: QualityDimensionState.SUPPORTED,
            QualityDimensionType.RIGHTS_USABILITY: (
                QualityDimensionState.SUPPORTED if rights is RightsUsability.USABLE
                else QualityDimensionState.BLOCKED if rights is RightsUsability.BLOCKED
                else QualityDimensionState.UNKNOWN
            ),
            QualityDimensionType.TEMPORAL_CONTINUITY: (
                QualityDimensionState.SUPPORTED if detail.previous_observation_id
                else QualityDimensionState.UNKNOWN
            ),
        }
        for dimension, state in dimensions.items():
            self.session.add(EvidenceQualityDimension(
                evidence_package_id=package.id,
                dimension=dimension,
                state=state,
                method_key=f"OWNED_SURFACE_{dimension.value}_V1",
                method_version=METHOD_VERSION,
                reasons_json=["Deterministic owned-surface observation assessment."],
            ))
        self.session.add(EvidencePackageItem(
            evidence_package_id=package.id,
            evidence_key=str(observation.id),
            evidence_type="OWNED_SURFACE_OBSERVATION",
            evidence_reference_id=observation.id,
            evidence_role="TARGET_PAGE_CONTENT",
            root_source_key="direct_http",
            independence=SourceIndependenceState.SAME_ROOT_SOURCE,
            method_compatibility=EvidenceCompatibility.COMPATIBLE,
            scope_compatibility=EvidenceCompatibility.COMPATIBLE,
            rights_usability=rights,
            supports_claim=rights is RightsUsability.USABLE,
            metadata_json={
                "url": observation.normalized_url,
                "change_classification": detail.change_classification,
                "render_state": detail.render_state,
            },
        ))
        # Existing gaps remain open; the candidate evidence is now explicitly reassessment-ready.
        gaps = self.session.scalars(select(EvidenceGap).where(
            EvidenceGap.collection_target_id == detail.collection_target_id,
            EvidenceGap.gap_type == "TARGET_PAGE_CONTENT_OBSERVATION",
            EvidenceGap.resolved_at.is_(None),
        )).all()
        for gap in gaps if detail.reassessment_ready else []:
            gap.provenance_metadata = {
                **gap.provenance_metadata,
                "reassessment_ready": True,
                "candidate_evidence_package_id": str(package.id),
                "candidate_observation_id": str(observation.id),
            }
        return package
