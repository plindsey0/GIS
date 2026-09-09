from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal, Optional
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.intelligence.prompts import PROMPT_VERSIONS, system_prompt
from gis.intelligence.provider import LLMProvider
from gis.intelligence.schemas import QueryPageIntentOutput
from gis.models import (
    AnalyticalEntity,
    AnalyticalEntityType,
    CompetitiveContentComponent,
    CompetitiveContentDocument,
    CompetitiveContentHeading,
    CompetitiveContentObservation,
    EvidencePackage,
    ExternalKeywordRanking,
    ExternalSearchObservation,
    GSCSearchObservation,
    LLMRun,
    QueryPageIntentAssessment,
    QueryPageIntentEvidence,
    QueryPageIntentReview,
    RightsUsability,
    SerpObservation,
    SerpResult,
    TrackedQuery,
)

METHOD_VERSION = "query_page_intent_resolution_v1"
SEMANTIC_STATES = {
    "SUPPORTED",
    "PARTIAL",
    "NOT_SUPPORTED",
    "UNRESOLVED",
    "INSUFFICIENT_EVIDENCE",
    "CONFLICTING_EVIDENCE",
}
ASSOCIATION_TYPES = {
    "GSC_SEARCH_OBSERVATION",
    "EXTERNAL_KEYWORD_RANKING",
    "SERP_RESULT",
    "OBSERVED_QUERY_PAGE_ASSOCIATION",
}


class IntentResolutionError(ValueError):
    pass


class GovernedReference(BaseModel):
    reference_id: uuid.UUID
    reference_type: str
    evidence_package_ids: list[uuid.UUID] = Field(min_length=1)
    exact_query: str
    page_url: Optional[str] = None
    market_definition_id: Optional[uuid.UUID] = None
    root_source: Optional[str] = None
    provider_declared_intent: Optional[str] = None


class QueryPageIntentContext(BaseModel):
    tenant_id: uuid.UUID
    site_id: uuid.UUID
    query_entity_id: uuid.UUID
    page_entity_id: uuid.UUID
    market_definition_id: Optional[uuid.UUID] = None
    exact_query: str
    candidate_url: str
    references: list[GovernedReference] = Field(min_length=1, max_length=80)
    page_content_claims: list[str] = Field(default_factory=list, max_length=30)
    serp_claims: list[str] = Field(default_factory=list, max_length=30)
    page_content_fingerprint: Optional[str] = None
    serp_fingerprint: Optional[str] = None
    quality: dict[str, object] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list, max_length=30)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, default=str, sort_keys=True).encode()).hexdigest()


def normalize_query(value: str) -> str:
    return " ".join(value.casefold().split())


def normalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if not parts.scheme or not parts.hostname:
        raise IntentResolutionError("Candidate page must be an absolute governed URL.")
    host = parts.hostname.casefold().removeprefix("www.")
    port = f":{parts.port}" if parts.port else ""
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.casefold(), host + port, path, parts.query, ""))


class QueryPageIntentService:
    """Neuro-symbolic exact-query/page resolution with deterministic trust boundaries."""

    def __init__(self, session: Session, provider: LLMProvider) -> None:
        self.session = session
        self.provider = provider

    def assemble_context(
        self,
        *,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        query_entity_id: uuid.UUID,
        page_entity_id: uuid.UUID,
        evidence_package_ids: list[uuid.UUID],
        market_definition_id: uuid.UUID | None = None,
    ) -> QueryPageIntentContext:
        """Assemble bounded authoritative observations; never invokes a provider or collector."""
        query_entity = self.session.get(AnalyticalEntity, query_entity_id)
        page_entity = self.session.get(AnalyticalEntity, page_entity_id)
        if not query_entity or not page_entity:
            raise IntentResolutionError("Governed query/page identity is missing.")
        exact_query = query_entity.canonical_key
        candidate_url = page_entity.canonical_key
        normalized_candidate = normalize_url(candidate_url)
        references: list[GovernedReference] = []

        def add_reference(
            reference_id: uuid.UUID,
            reference_type: str,
            *,
            page_url: str | None,
            root_source: str,
            provider_intent: str | None = None,
        ) -> None:
            references.append(GovernedReference(
                reference_id=reference_id,
                reference_type=reference_type,
                evidence_package_ids=evidence_package_ids,
                exact_query=exact_query,
                page_url=page_url,
                market_definition_id=market_definition_id,
                root_source=root_source,
                provider_declared_intent=provider_intent,
            ))

        gsc = list(self.session.scalars(select(GSCSearchObservation).where(
            GSCSearchObservation.tenant_id == tenant_id,
            GSCSearchObservation.site_id == site_id,
            GSCSearchObservation.effective_end.is_(None),
        ).order_by(GSCSearchObservation.observed_at.desc()).limit(100)))
        for row in gsc:
            if row.query and row.page and normalize_query(row.query) == normalize_query(exact_query):
                if normalize_url(row.page) == normalized_candidate:
                    add_reference(row.id, "GSC_SEARCH_OBSERVATION", page_url=row.page, root_source="google_search_console")

        rankings = self.session.execute(
            select(ExternalKeywordRanking, ExternalSearchObservation)
            .join(ExternalSearchObservation)
            .where(
                ExternalSearchObservation.tenant_id == tenant_id,
                ExternalSearchObservation.site_id == site_id,
                ExternalSearchObservation.effective_end.is_(None),
            )
            .order_by(ExternalSearchObservation.observed_at.desc())
            .limit(100)
        ).all()
        for ranking, _ in rankings:
            if normalize_query(ranking.normalized_keyword) == normalize_query(exact_query):
                ranking_url = ranking.ranking_url or ranking.normalized_url
                if ranking_url and normalize_url(ranking_url) == normalized_candidate:
                    add_reference(
                        ranking.id,
                        "EXTERNAL_KEYWORD_RANKING",
                        page_url=ranking_url,
                        root_source="dataforseo",
                        provider_intent=ranking.search_intent,
                    )

        serp_rows = self.session.execute(
            select(SerpResult, SerpObservation, TrackedQuery)
            .join(SerpObservation, SerpObservation.id == SerpResult.serp_observation_id)
            .join(TrackedQuery, TrackedQuery.id == SerpObservation.tracked_query_id)
            .where(SerpObservation.tenant_id == tenant_id, SerpObservation.site_id == site_id)
            .order_by(SerpObservation.observed_at.desc(), SerpResult.rank_absolute)
            .limit(100)
        ).all()
        serp_claims: list[str] = []
        latest_serp: SerpObservation | None = None
        for result, observation, tracked in serp_rows:
            if normalize_query(tracked.normalized_query) != normalize_query(exact_query):
                continue
            latest_serp = latest_serp or observation
            if result.title:
                claim = f"Exact SERP result {result.rank_absolute}: {result.title}"
                if claim not in serp_claims and len(serp_claims) < 20:
                    serp_claims.append(claim)
            if result.normalized_url and normalize_url(result.normalized_url) == normalized_candidate:
                add_reference(result.id, "SERP_RESULT", page_url=result.normalized_url, root_source="exact_serp")

        content = self.session.scalar(select(CompetitiveContentObservation).where(
            CompetitiveContentObservation.tenant_id == tenant_id,
            CompetitiveContentObservation.site_id == site_id,
            CompetitiveContentObservation.effective_end.is_(None),
            CompetitiveContentObservation.normalized_url == normalized_candidate,
        ).order_by(CompetitiveContentObservation.observed_at.desc()))
        page_claims: list[str] = []
        if content:
            document = self.session.get(CompetitiveContentDocument, content.id)
            if document and document.title:
                page_claims.append(f"Observed page title: {document.title}")
            headings = list(self.session.scalars(select(CompetitiveContentHeading).where(
                CompetitiveContentHeading.observation_id == content.id
            ).order_by(CompetitiveContentHeading.ordinal).limit(15)))
            page_claims.extend(f"Observed H{row.level}: {row.heading_text}" for row in headings)
            components = list(self.session.scalars(select(CompetitiveContentComponent).where(
                CompetitiveContentComponent.observation_id == content.id
            ).order_by(CompetitiveContentComponent.component_type).limit(10)))
            page_claims.extend(
                f"Observed component: {row.component_type} ({row.occurrence_count})"
                for row in components
            )
            add_reference(content.id, "OWNED_PAGE_CONTENT_OBSERVATION", page_url=candidate_url, root_source="owned_content")
        limitations = []
        if not content:
            limitations.append("No governed current page-content observation was available.")
        if not latest_serp:
            limitations.append("No governed exact-query SERP observation was available.")
        if not references:
            # The context remains constructible so callers can resolve insufficient evidence.
            references.append(GovernedReference(
                reference_id=uuid.uuid5(uuid.NAMESPACE_URL, f"gis:query-page-candidate:{query_entity_id}:{page_entity_id}"),
                reference_type="GOVERNED_QUERY_PAGE_CANDIDATE",
                evidence_package_ids=evidence_package_ids,
                exact_query=exact_query,
                page_url=None,
                market_definition_id=market_definition_id,
                root_source="governed_identity",
            ))
        return QueryPageIntentContext(
            tenant_id=tenant_id,
            site_id=site_id,
            query_entity_id=query_entity_id,
            page_entity_id=page_entity_id,
            market_definition_id=market_definition_id,
            exact_query=exact_query,
            candidate_url=candidate_url,
            references=references,
            page_content_claims=page_claims,
            serp_claims=serp_claims,
            page_content_fingerprint=content.content_hash if content else None,
            serp_fingerprint=latest_serp.observation_key if latest_serp else None,
            limitations=limitations,
        )

    def _validate_context(self, context: QueryPageIntentContext) -> dict[uuid.UUID, GovernedReference]:
        query = self.session.get(AnalyticalEntity, context.query_entity_id)
        page = self.session.get(AnalyticalEntity, context.page_entity_id)
        for entity, expected in ((query, AnalyticalEntityType.QUERY), (page, AnalyticalEntityType.URL)):
            if not entity or entity.tenant_id != context.tenant_id or entity.site_id != context.site_id:
                raise IntentResolutionError("Query/page entity is outside tenant/site scope.")
            if entity.entity_type != expected:
                raise IntentResolutionError(f"Expected {expected.value} analytical entity.")
        assert query is not None and page is not None
        if normalize_query(query.canonical_key) != normalize_query(context.exact_query):
            raise IntentResolutionError("Exact query differs from governed query identity.")
        if normalize_url(page.canonical_key) != normalize_url(context.candidate_url):
            raise IntentResolutionError("Candidate URL differs from governed page identity.")
        registry = {row.reference_id: row for row in context.references}
        if len(registry) != len(context.references):
            raise IntentResolutionError("Duplicate governed reference IDs are not allowed.")
        for reference in context.references:
            if normalize_query(reference.exact_query) != normalize_query(context.exact_query):
                raise IntentResolutionError("Related query was substituted for the exact query.")
            if reference.page_url and normalize_url(reference.page_url) != normalize_url(
                context.candidate_url
            ):
                raise IntentResolutionError("Evidence references a different candidate page.")
            if reference.market_definition_id not in {None, context.market_definition_id}:
                raise IntentResolutionError("Evidence market is incompatible with governed market.")
            for package_id in reference.evidence_package_ids:
                package = self.session.get(EvidencePackage, package_id)
                if not package or package.tenant_id != context.tenant_id or package.site_id != context.site_id:
                    raise IntentResolutionError("Evidence package is outside tenant/site scope.")
                if package.analytical_entity_id != context.query_entity_id:
                    raise IntentResolutionError("Evidence package is outside exact-query entity scope.")
                if package.market_definition_id not in {None, context.market_definition_id}:
                    raise IntentResolutionError("Evidence package market is incompatible.")
                if package.rights_usability not in {
                    RightsUsability.USABLE,
                    RightsUsability.PARTIALLY_USABLE,
                }:
                    raise IntentResolutionError("Evidence package rights are unusable.")
                if not package.quality_run_id or not package.method_version:
                    raise IntentResolutionError("Evidence package provenance is incomplete.")
        return registry

    @staticmethod
    def association_state(context: QueryPageIntentContext) -> str:
        roots = {
            reference.root_source or reference.reference_type
            for reference in context.references
            if reference.reference_type in ASSOCIATION_TYPES and reference.page_url
        }
        return "SUPPORTED" if roots else "NOT_OBSERVED"

    def resolve(self, context: QueryPageIntentContext) -> QueryPageIntentAssessment:
        registry = self._validate_context(context)
        payload = context.model_dump(mode="json")
        fingerprint = _digest(
            {"method": METHOD_VERSION, "provider": self.provider.key, "model": self.provider.model_identifier, "context": payload}
        )
        existing = self.session.scalar(
            select(QueryPageIntentAssessment).where(
                QueryPageIntentAssessment.input_fingerprint == fingerprint
            )
        )
        if existing:
            return existing
        result = self.provider.generate_structured(
            task="query_page_intent_resolution",
            system_prompt=system_prompt("query_page_intent_resolution"),
            user_prompt="GOVERNED CONTEXT\n" + json.dumps(payload, sort_keys=True),
            response_schema=QueryPageIntentOutput,
            metadata={"prompt_version": PROMPT_VERSIONS["query_page_intent_resolution"]},
        )
        output = QueryPageIntentOutput.model_validate(result.value)
        run = LLMRun(
            tenant_id=context.tenant_id,
            site_id=context.site_id,
            task_type="query_page_intent_resolution",
            provider_key=result.provider,
            model_identifier=result.model,
            prompt_version=PROMPT_VERSIONS["query_page_intent_resolution"],
            request_fingerprint=fingerprint,
            input_evidence_ids_json=sorted(map(str, registry)),
            input_opportunity_ids_json=[],
            input_recommendation_ids_json=[],
            response_snapshot_json=output.model_dump(mode="json"),
            validation_status="PENDING",
            validation_errors_json=[],
            provider_metadata_json=result.metadata,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            provider_cost=Decimal(str(result.cost)) if result.cost is not None else None,
        )
        self.session.add(run)
        self.session.flush()
        errors = self._validate_output(context, output, registry)
        if errors:
            run.validation_status = "INVALID"
            run.validation_errors_json = errors
            self.session.flush()
            self.session.info["failed_llm_run_snapshot"] = {
                column.key: getattr(run, column.key) for column in LLMRun.__table__.columns
            }
            raise IntentResolutionError("; ".join(errors))
        run.validation_status = "VALID"
        previous = self.session.scalar(
            select(QueryPageIntentAssessment)
            .where(
                QueryPageIntentAssessment.tenant_id == context.tenant_id,
                QueryPageIntentAssessment.site_id == context.site_id,
                QueryPageIntentAssessment.query_entity_id == context.query_entity_id,
                QueryPageIntentAssessment.page_entity_id == context.page_entity_id,
                QueryPageIntentAssessment.is_current.is_(True),
            )
            .order_by(QueryPageIntentAssessment.evaluated_at.desc())
        )
        if previous:
            previous.is_current = False
        assessment = QueryPageIntentAssessment(
            tenant_id=context.tenant_id,
            site_id=context.site_id,
            query_entity_id=context.query_entity_id,
            page_entity_id=context.page_entity_id,
            market_definition_id=context.market_definition_id,
            query_text=context.exact_query,
            page_url=context.candidate_url,
            association_state=self.association_state(context),
            targeting_state=output.targeting_state,
            intent_satisfaction_state=output.intent_satisfaction_state,
            interpreted_user_need=output.interpreted_user_need,
            origin="MODEL" if self.provider.external else "REPLAY",
            method_key="governed_query_page_intent_resolution",
            method_version=METHOD_VERSION,
            prompt_version=PROMPT_VERSIONS["query_page_intent_resolution"],
            llm_run_id=run.id,
            previous_assessment_id=previous.id if previous else None,
            input_fingerprint=fingerprint,
            page_content_fingerprint=context.page_content_fingerprint,
            serp_fingerprint=context.serp_fingerprint,
            supporting_references_json=[registry[item].model_dump(mode="json") for item in output.supporting_evidence_ids],
            conflicting_references_json=[registry[item].model_dump(mode="json") for item in output.conflicting_evidence_ids],
            rationale=output.reasoning_summary,
            assumptions_json=output.assumptions,
            limitations_json=[*context.limitations, *output.limitations],
            evidence_gaps_json=[{"gap_type": item, "status": "UNRESOLVED"} for item in output.evidence_gap_types],
            quality_json={**context.quality, "confidence_metadata": output.confidence_metadata},
            is_current=True,
            reassessment_needed=False,
            reassessment_reasons_json=[],
            evaluated_at=datetime.now(timezone.utc),
        )
        self.session.add(assessment)
        self.session.flush()
        package_ids = sorted(
            {package_id for reference in context.references for package_id in reference.evidence_package_ids},
            key=str,
        )
        self.session.add_all(
            [QueryPageIntentEvidence(assessment_id=assessment.id, evidence_package_id=item) for item in package_ids]
        )
        return assessment

    @staticmethod
    def _validate_output(
        context: QueryPageIntentContext,
        output: QueryPageIntentOutput,
        registry: dict[uuid.UUID, GovernedReference],
    ) -> list[str]:
        errors: list[str] = []
        cited = set(output.supporting_evidence_ids) | set(output.conflicting_evidence_ids)
        if normalize_query(output.query) != normalize_query(context.exact_query):
            errors.append("Model changed the governed exact query.")
        try:
            if normalize_url(output.candidate_url) != normalize_url(context.candidate_url):
                errors.append("Model changed the governed candidate URL.")
        except IntentResolutionError:
            errors.append("Model returned an invalid candidate URL.")
        if cited - set(registry):
            errors.append("Model cited evidence outside the governed context.")
        if not set(output.page_content_claims) <= set(context.page_content_claims):
            errors.append("Model asserted page content absent from governed page evidence.")
        if not set(output.serp_claims) <= set(context.serp_claims):
            errors.append("Model asserted SERP conditions absent from governed SERP evidence.")
        association = QueryPageIntentService.association_state(context)
        if association != "SUPPORTED" and output.intent_satisfaction_state == "SUPPORTED":
            errors.append("Model promoted absent association into supported satisfaction.")
        if output.targeting_state == "NOT_SUPPORTED" and output.intent_satisfaction_state == "SUPPORTED":
            errors.append("Targeting and satisfaction states materially contradict one another.")
        if not context.page_content_claims and output.targeting_state not in {
            "UNRESOLVED", "INSUFFICIENT_EVIDENCE"
        }:
            errors.append("Targeting conclusion exceeds missing page-content evidence.")
        if not context.serp_claims and output.intent_satisfaction_state == "SUPPORTED":
            errors.append("Supported satisfaction exceeds missing exact-query SERP evidence.")
        return errors

    def mark_reassessment_needed(
        self, assessment_id: uuid.UUID, *, page_fingerprint: str | None, serp_fingerprint: str | None
    ) -> QueryPageIntentAssessment:
        assessment = self.session.get(QueryPageIntentAssessment, assessment_id)
        if not assessment:
            raise IntentResolutionError("Assessment not found.")
        reasons = []
        if page_fingerprint and page_fingerprint != assessment.page_content_fingerprint:
            reasons.append("PAGE_CONTENT_CHANGED")
        if serp_fingerprint and serp_fingerprint != assessment.serp_fingerprint:
            reasons.append("EXACT_SERP_CHANGED")
        assessment.reassessment_needed = bool(reasons)
        assessment.reassessment_reasons_json = reasons
        return assessment

    def review(
        self,
        assessment_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        decision: Literal["CONFIRM", "DISAGREE", "NEEDS_MORE_EVIDENCE"],
        reviewer: str,
        comment: str | None = None,
    ) -> QueryPageIntentReview:
        assessment = self.session.get(QueryPageIntentAssessment, assessment_id)
        if not assessment or assessment.tenant_id != tenant_id or assessment.site_id != site_id:
            raise IntentResolutionError("Assessment not found in tenant/site scope.")
        review = QueryPageIntentReview(
            assessment_id=assessment.id,
            decision=decision,
            reviewer=reviewer,
            comment=comment,
            reviewed_at=datetime.now(timezone.utc),
        )
        self.session.add(review)
        return review

    def read_model(self, assessment_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, Any]:
        assessment = self.session.get(QueryPageIntentAssessment, assessment_id)
        if not assessment or assessment.tenant_id != tenant_id or assessment.site_id != site_id:
            raise IntentResolutionError("Assessment not found in tenant/site scope.")
        reviews = list(
            self.session.scalars(
                select(QueryPageIntentReview)
                .where(QueryPageIntentReview.assessment_id == assessment.id)
                .order_by(QueryPageIntentReview.reviewed_at)
            )
        )
        latest = reviews[-1] if reviews else None
        run = self.session.get(LLMRun, assessment.llm_run_id) if assessment.llm_run_id else None
        return {
            "id": str(assessment.id),
            "resource_type": "query_page_intent",
            "label": f"{assessment.query_text} ↔ {assessment.page_url}",
            "exact_query": {"query": assessment.query_text, "market_id": str(assessment.market_definition_id) if assessment.market_definition_id else None},
            "candidate_page": {"url": assessment.page_url, "content_fingerprint": assessment.page_content_fingerprint},
            "relationship": {
                "association": assessment.association_state,
                "targeting": assessment.targeting_state,
                "intent_satisfaction": assessment.intent_satisfaction_state,
            },
            "why": assessment.rationale,
            "supporting_evidence": assessment.supporting_references_json,
            "conflicts": assessment.conflicting_references_json,
            "evidence_gaps": assessment.evidence_gaps_json,
            "limitations": assessment.limitations_json,
            "reassessment": {"needed": assessment.reassessment_needed, "reasons": assessment.reassessment_reasons_json},
            "human_review": {
                "current_disposition": latest.decision if latest else "UNREVIEWED",
                "history": [{"decision": row.decision, "reviewer": row.reviewer, "comment": row.comment, "reviewed_at": row.reviewed_at.isoformat()} for row in reviews],
            },
            "audit": {
                "origin": assessment.origin,
                "provider": run.provider_key if run else None,
                "model": run.model_identifier if run else None,
                "method": assessment.method_key,
                "method_version": assessment.method_version,
                "prompt_version": assessment.prompt_version,
                "llm_run_id": str(assessment.llm_run_id) if assessment.llm_run_id else None,
                "evidence_references": [
                    *assessment.supporting_references_json,
                    *assessment.conflicting_references_json,
                ],
                "evaluated_at": assessment.evaluated_at.isoformat(),
            },
        }
