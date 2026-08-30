from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.integrations.content_intelligence.extraction import extract_page, normalize_url
from gis.integrations.content_intelligence.retrieval import ContentRetriever
from gis.models import (
    CompetitiveContentCohort,
    CompetitiveContentCohortMember,
    CompetitiveContentComponent,
    CompetitiveContentDocument,
    CompetitiveContentHeading,
    CompetitiveContentLink,
    CompetitiveContentObservation,
    CompetitiveContentSchemaType,
    CompetitiveContentTerm,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    ExternalKeywordRanking,
    ExternalSearchObservation,
    IngestionRun,
    IngestionStatus,
    PermittedUse,
    SerpObservation,
    SerpResult,
    Site,
    TrackedQuery,
)
from gis.provenance.service import assert_use_allowed, evaluate_connection_use


@dataclass(frozen=True)
class ContentTarget:
    url: str
    tracked_query_id: uuid.UUID | None = None
    serp_result_id: uuid.UUID | None = None
    external_search_observation_id: uuid.UUID | None = None


def discover_content_targets(
    session: Session,
    site_id: uuid.UUID,
    *,
    tracked_query_id: uuid.UUID | None = None,
    external_search_observation_id: uuid.UUID | None = None,
    domain: str | None = None,
    limit: int = 10,
) -> list[ContentTarget]:
    if not 1 <= limit <= 20 or bool(tracked_query_id) == bool(external_search_observation_id):
        raise ValueError("select exactly one discovery source and a limit from 1-20")
    site = session.get(Site, site_id)
    if not site:
        raise ValueError("site not found")
    if tracked_query_id:
        query = session.get(TrackedQuery, tracked_query_id)
        if not query or query.tenant_id != site.tenant_id or query.site_id != site.id:
            raise ValueError("tracked query does not belong to site")
        serp = session.scalar(
            select(SerpObservation)
            .where(
                SerpObservation.tracked_query_id == query.id,
                SerpObservation.effective_end.is_(None),
            )
            .order_by(SerpObservation.observed_at.desc())
            .limit(1)
        )
        if not serp:
            return []
        statement = (
            select(SerpResult)
            .where(
                SerpResult.serp_observation_id == serp.id,
                SerpResult.is_organic.is_(True),
                SerpResult.normalized_url.is_not(None),
            )
            .order_by(SerpResult.rank_absolute)
            .limit(limit)
        )
        if domain:
            statement = statement.where(SerpResult.hostname == domain.casefold())
        return [
            ContentTarget(str(row.normalized_url), query.id, row.id, None)
            for row in session.scalars(statement).all()
        ]
    observation = session.get(ExternalSearchObservation, external_search_observation_id)
    if not observation or observation.tenant_id != site.tenant_id or observation.site_id != site.id:
        raise ValueError("external-search observation does not belong to site")
    external_statement = (
        select(ExternalKeywordRanking)
        .where(
            ExternalKeywordRanking.external_search_observation_id == observation.id,
            ExternalKeywordRanking.normalized_url != "",
        )
        .order_by(ExternalKeywordRanking.position)
        .limit(limit)
    )
    if domain:
        external_statement = external_statement.where(
            ExternalKeywordRanking.ranking_domain == domain.casefold()
        )
    return [
        ContentTarget(str(row.normalized_url), None, None, observation.id)
        for row in session.scalars(external_statement).all()
    ]


class CompetitiveContentCollector:
    def __init__(self, session: Session, retriever: ContentRetriever) -> None:
        self.session, self.retriever = session, retriever

    def collect(
        self,
        connection_id: uuid.UUID,
        site_id: uuid.UUID,
        url: str,
        *,
        tracked_query_id: uuid.UUID | None = None,
        serp_result_id: uuid.UUID | None = None,
        external_search_observation_id: uuid.UUID | None = None,
        estimated_cost: Decimal | None = Decimal("0"),
    ) -> IngestionRun:
        connection = self.session.get(DataSourceConnection, connection_id)
        site = self.session.get(Site, site_id)
        if not connection or not site or connection.tenant_id != site.tenant_id:
            raise ValueError("content connection/site scope mismatch")
        if connection.site_id is not None and connection.site_id != site.id:
            raise ValueError("site-scoped connection cannot collect for another site")
        source = self.session.get(DataSource, connection.data_source_id)
        policy_id = connection.rights_policy_id or (
            source.default_rights_policy_id if source else None
        )
        policy = self.session.get(DataRightsPolicy, policy_id) if policy_id else None
        if not source or not policy:
            raise ValueError("content source and rights policy are required")
        assert_use_allowed(
            evaluate_connection_use(self.session, connection, PermittedUse.NORMALIZED_RETENTION)
        )
        normalized_requested, requested_domain, requested_path = normalize_url(url)
        now = datetime.now(timezone.utc)
        run = IngestionRun(
            tenant_id=site.tenant_id,
            site_id=site.id,
            data_source_connection_id=connection.id,
            started_at=now,
            status=IngestionStatus.RUNNING,
            rights_policy_id=policy.id,
            acquisition_method=source.acquisition_method,
            collector_name="gis.integrations.content_intelligence",
            collector_version="1",
            schema_version="1",
            source_metadata={"url": normalized_requested, "render_mode": "RAW_HTTP"},
        )
        self.session.add(run)
        self.session.flush()
        savepoint = self.session.begin_nested()
        try:
            retrieved = self.retriever.retrieve(normalized_requested)
            normalized_resolved, domain, page_path = normalize_url(retrieved.resolved_url)
            content_hash = hashlib.sha256(retrieved.body).hexdigest()
            identity = [
                str(site.id),
                normalized_requested,
                retrieved.retrieved_at.date().isoformat(),
            ]
            observation_key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
            current = self.session.scalar(
                select(CompetitiveContentObservation).where(
                    CompetitiveContentObservation.observation_key == observation_key,
                    CompetitiveContentObservation.effective_end.is_(None),
                )
            )
            if current and current.content_hash == content_hash:
                run.status = IngestionStatus.SUCCEEDED
                run.records_received = 1
                run.completed_at = datetime.now(timezone.utc)
                run.source_metadata = {**run.source_metadata, "idempotent_replay": True}
                savepoint.commit()
                self.session.commit()
                return run
            if current:
                current.effective_end = now
            page = extract_page(retrieved.body, normalized_resolved)
            owned_domain = normalize_url(site.canonical_url)[1]
            observation = CompetitiveContentObservation(
                tenant_id=site.tenant_id,
                organization_id=site.organization_id,
                site_id=site.id,
                data_source_connection_id=connection.id,
                ingestion_run_id=run.id,
                rights_policy_id=policy.id,
                rights_policy_version=policy.policy_version,
                requested_url=url,
                normalized_url=normalized_requested,
                resolved_url=normalized_resolved,
                canonical_url=page.canonical_url,
                domain=domain,
                page_path=page_path,
                ownership_class="OWNED" if domain == owned_domain else "COMPETITOR",
                tracked_query_id=tracked_query_id,
                serp_result_id=serp_result_id,
                external_search_observation_id=external_search_observation_id,
                observed_at=retrieved.retrieved_at,
                retrieved_at=retrieved.retrieved_at,
                retrieval_status=(
                    "HTTP_SUCCESS" if 200 <= retrieved.status_code < 300 else "HTTP_ERROR"
                ),
                http_status=retrieved.status_code,
                render_mode="RAW_HTTP",
                content_type=retrieved.content_type,
                content_language=page.language or retrieved.headers.get("Content-Language"),
                response_bytes=len(retrieved.body),
                content_hash=content_hash,
                observation_key=observation_key,
                estimated_cost=estimated_cost,
                cost_currency="USD",
                raw_payload_reference=None,
                raw_retained=False,
                truncated=retrieved.truncated,
                retrieval_metadata={
                    "raw_retention": "HASH_AND_EXTRACTED_FEATURES_ONLY",
                    "javascript_rendered": False,
                    "http_last_modified": retrieved.headers.get("Last-Modified"),
                },
                effective_start=now,
            )
            self.session.add(observation)
            self.session.flush()
            self._persist_features(observation, page)
            run.status = IngestionStatus.SUCCEEDED
            run.records_received = 1
            run.records_inserted = 1
            run.completed_at = datetime.now(timezone.utc)
            savepoint.commit()
        except Exception as error:
            savepoint.rollback()
            run.status = IngestionStatus.FAILED
            run.error_count = 1
            run.error_summary = f"{type(error).__name__}: {error}"[:1000]
            run.completed_at = datetime.now(timezone.utc)
        self.session.commit()
        return run

    def _persist_features(self, observation: CompetitiveContentObservation, page: object) -> None:
        from gis.integrations.content_intelligence.extraction import ExtractedPage

        if not isinstance(page, ExtractedPage):
            raise TypeError("unexpected extracted page")
        internal_count = sum(link["class"] == "INTERNAL" for link in page.links)
        external_count = sum(link["class"] == "EXTERNAL" for link in page.links)
        self.session.add(
            CompetitiveContentDocument(
                observation_id=observation.id,
                title=page.title,
                meta_description=page.meta_description,
                robots_directives=sorted(set(page.robots)),
                normalized_word_count=page.word_count,
                paragraph_count=page.paragraph_count,
                h1_count=page.tag_counts["h1"],
                h2_count=page.tag_counts["h2"],
                h3_count=page.tag_counts["h3"],
                ordered_list_count=page.tag_counts["ol"],
                unordered_list_count=page.tag_counts["ul"],
                table_count=page.tag_counts["table"],
                image_count=page.tag_counts["img"],
                video_count=page.tag_counts["video"] + page.tag_counts["embed"],
                form_count=page.tag_counts["form"],
                iframe_count=page.tag_counts["iframe"],
                internal_link_count=internal_count,
                external_link_count=external_count,
                publication_dates=page.publication_dates,
                modified_dates=page.modified_dates,
                metric_semantics={"dom_counts": "MEASURED", "visible_text": "GIS_DERIVED"},
            )
        )
        for ordinal, (level, text) in enumerate(page.headings, 1):
            self.session.add(
                CompetitiveContentHeading(
                    observation_id=observation.id,
                    ordinal=ordinal,
                    level=level,
                    heading_text=text,
                    normalized_text=text.casefold(),
                )
            )
        for schema_type, count in page.schema_types.items():
            self.session.add(
                CompetitiveContentSchemaType(
                    observation_id=observation.id, schema_type=schema_type, occurrence_count=count
                )
            )
        for link in page.links:
            rel_values = link["rel"] if isinstance(link["rel"], list) else []
            self.session.add(
                CompetitiveContentLink(
                    observation_id=observation.id,
                    target_url=str(link["url"]),
                    target_domain=str(link["domain"]),
                    link_class=str(link["class"]),
                    anchor_text=str(link["anchor"]) if link.get("anchor") else None,
                    rel_values=[str(value) for value in rel_values],
                )
            )
        for component in page.components:
            self.session.add(
                CompetitiveContentComponent(
                    observation_id=observation.id,
                    component_type=str(component["type"]),
                    occurrence_count=int(str(component["count"])),
                    detection_method=str(component["method"]),
                    confidence=Decimal(str(component["confidence"])),
                    metric_semantics=str(component["semantics"]),
                    evidence={},
                )
            )
        for term, count in page.terms.items():
            self.session.add(
                CompetitiveContentTerm(
                    observation_id=observation.id,
                    term=term,
                    normalized_term=term,
                    occurrence_count=count,
                    extraction_method="HEADING_NGRAM_V1",
                    metric_semantics="GIS_DERIVED",
                )
            )


def create_cohort(
    session: Session,
    site_id: uuid.UUID,
    name: str,
    observation_ids: list[uuid.UUID],
    *,
    tracked_query_id: uuid.UUID | None = None,
    rank_positions: dict[uuid.UUID, int] | None = None,
) -> CompetitiveContentCohort:
    site = session.get(Site, site_id)
    if not site or not observation_ids or len(observation_ids) > 100:
        raise ValueError("cohort requires a site and 1-100 observations")
    observations = session.scalars(
        select(CompetitiveContentObservation).where(
            CompetitiveContentObservation.id.in_(observation_ids)
        )
    ).all()
    if len(observations) != len(set(observation_ids)) or any(
        item.tenant_id != site.tenant_id or item.site_id != site.id for item in observations
    ):
        raise ValueError("cohort observations must belong to the requested site")
    cohort = CompetitiveContentCohort(
        tenant_id=site.tenant_id,
        organization_id=site.organization_id,
        site_id=site.id,
        tracked_query_id=tracked_query_id,
        name=name,
        definition={"member_count": len(observation_ids), "immutable_membership": True},
        frozen_at=datetime.now(timezone.utc),
    )
    session.add(cohort)
    session.flush()
    for observation_id in observation_ids:
        session.add(
            CompetitiveContentCohortMember(
                cohort_id=cohort.id,
                observation_id=observation_id,
                rank_position=(rank_positions or {}).get(observation_id),
                membership_source="EXPLICIT",
            )
        )
    session.commit()
    return cohort
