from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.integrations.external_search.scope import country_scope
from gis.market_intelligence.analysis import (
    CLASSIFICATION_METHOD,
    CLASSIFICATION_VERSION,
    METHOD_KEY,
    METHOD_VERSION,
    classify_intent,
    coverage_status,
    effective_competitor_count,
    hhi,
    participant_class,
    reciprocal_rank,
    shares,
)
from gis.models import (
    DataRightsPolicy,
    EventSemanticClass,
    ExternalKeywordRanking,
    ExternalSearchObservation,
    MarketCoverageStatus,
    MarketDefinition,
    MarketDefinitionMember,
    MarketInclusion,
    MarketMemberType,
    MarketMetricDefinition,
    MarketMetricObservation,
    MarketObservation,
    MarketParticipantClass,
    MarketParticipantObservation,
    MarketSegmentObservation,
    MarketStatus,
    MarketType,
    ResultOwnership,
    RightsDecision,
    SerpObservation,
    SerpResult,
    Site,
    TrackedQuery,
)

MAX_MARKET_MEMBERS = 500
MAX_RESULTS = 50_000


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _require_rights(policy: DataRightsPolicy) -> None:
    required = {
        "deterministic_analysis_allowed": policy.deterministic_analysis_allowed,
        "derived_storage_allowed": policy.derived_storage_allowed,
        "aggregation_allowed": policy.aggregation_allowed,
    }
    blocked = {
        key: value.value for key, value in required.items() if value is not RightsDecision.ALLOWED
    }
    if blocked:
        raise PermissionError(f"market synthesis denied by rights policy: {blocked}")


class MarketIntelligenceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def define(
        self,
        *,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        name: str,
        slug: str,
        tracked_query_ids: Sequence[uuid.UUID],
        market_type: MarketType = MarketType.SEARCH_MARKET,
        description: str | None = None,
        created_by: str | None = None,
        effective_at: datetime | None = None,
    ) -> MarketDefinition:
        if not tracked_query_ids or len(tracked_query_ids) > MAX_MARKET_MEMBERS:
            raise ValueError(f"tracked queries must contain 1..{MAX_MARKET_MEMBERS} members")
        site = self.session.scalar(
            select(Site).where(Site.tenant_id == tenant_id, Site.id == site_id)
        )
        if not site:
            raise ValueError("site not found in tenant")
        query_rows = self.session.scalars(
            select(TrackedQuery).where(
                TrackedQuery.tenant_id == tenant_id,
                TrackedQuery.site_id == site_id,
                TrackedQuery.id.in_(set(tracked_query_ids)),
            )
        ).all()
        if len(query_rows) != len(set(tracked_query_ids)):
            raise ValueError("one or more tracked queries are outside the tenant/site scope")
        contexts = {(query.country_code, query.language_code, query.device) for query in query_rows}
        if len(contexts) != 1:
            raise ValueError("a market definition cannot mix country, language, or device contexts")
        country_code, language_code, device = next(iter(contexts))
        now = effective_at or datetime.now(timezone.utc)
        previous = self.session.scalar(
            select(MarketDefinition)
            .where(
                MarketDefinition.tenant_id == tenant_id,
                MarketDefinition.site_id == site_id,
                MarketDefinition.slug == slug,
                MarketDefinition.status == MarketStatus.ACTIVE,
            )
            .order_by(MarketDefinition.version.desc())
        )
        version = (previous.version + 1) if previous else 1
        definition = MarketDefinition(
            tenant_id=tenant_id,
            organization_id=site.organization_id,
            site_id=site_id,
            name=name,
            slug=slug,
            description=description,
            status=MarketStatus.ACTIVE,
            market_type=market_type,
            country_code=country_code,
            language_code=language_code,
            device=device,
            version=version,
            effective_at=now,
            supersedes_id=previous.id if previous else None,
            created_by=created_by,
            semantic_notes={"frozen_members": True, "member_count": len(query_rows)},
        )
        self.session.add(definition)
        self.session.flush()
        for rank, query in enumerate(sorted(query_rows, key=lambda row: row.normalized_query), 1):
            self.session.add(
                MarketDefinitionMember(
                    market_definition_id=definition.id,
                    member_type=MarketMemberType.TRACKED_QUERY,
                    member_key=query.normalized_query,
                    member_uuid=query.id,
                    inclusion=MarketInclusion.INCLUDE,
                    weight=Decimal(1),
                    rank_order=rank,
                    effective_start=now,
                    provenance_metadata={"source": "gis_core.tracked_query"},
                )
            )
        if previous:
            previous.status = MarketStatus.SUPERSEDED
            previous.superseded_at = now
        self.session.flush()
        return definition

    def validate(self, definition: MarketDefinition) -> dict[str, object]:
        members = self.session.scalars(
            select(MarketDefinitionMember).where(
                MarketDefinitionMember.market_definition_id == definition.id
            )
        ).all()
        return {
            "valid": bool(members),
            "definition_id": definition.id,
            "version": definition.version,
            "frozen_member_count": len(members),
            "supported_member_types": sorted({item.member_type.value for item in members}),
        }

    def ensure_metric_definitions(self) -> dict[str, MarketMetricDefinition]:
        specifications = (
            (
                "OBSERVED_QUERY_COUNT",
                "Observed query count",
                "Queries with evidence in the frozen definition",
                "count",
                EventSemanticClass.MEASURED,
            ),
            (
                "OBSERVED_DOMAIN_COUNT",
                "Observed domain count",
                "Unique participant domains in observed organic results",
                "count",
                EventSemanticClass.MEASURED,
            ),
            (
                "MARKET_HHI",
                "Observed visibility HHI",
                "Sum of squared reciprocal-rank visibility shares",
                "ratio",
                EventSemanticClass.GIS_DERIVED,
            ),
            (
                "EFFECTIVE_COMPETITOR_COUNT",
                "Effective participant count",
                "Reciprocal of observed visibility HHI",
                "count",
                EventSemanticClass.GIS_DERIVED,
            ),
            (
                "TOTAL_PROVIDER_SEARCH_VOLUME",
                "Provider-reported search volume",
                "Unique-query provider volume; incomplete and not GSC impressions",
                "searches",
                EventSemanticClass.PROVIDER_REPORTED,
            ),
            (
                "QUERY_COVERAGE_RATE",
                "Query coverage rate",
                "Observed frozen queries divided by configured frozen queries",
                "ratio",
                EventSemanticClass.GIS_DERIVED,
            ),
        )
        definitions: dict[str, MarketMetricDefinition] = {}
        for key, name, description, unit, semantic in specifications:
            method = (
                "PROVIDER_REPORTED_SEARCH_VOLUME"
                if key == "TOTAL_PROVIDER_SEARCH_VOLUME"
                else METHOD_KEY
            )
            row = self.session.scalar(
                select(MarketMetricDefinition).where(
                    MarketMetricDefinition.metric_key == key,
                    MarketMetricDefinition.method_key == method,
                    MarketMetricDefinition.method_version == METHOD_VERSION,
                )
            )
            if not row:
                row = MarketMetricDefinition(
                    metric_key=key,
                    display_name=name,
                    description=description,
                    unit=unit,
                    method_key=method,
                    method_version=METHOD_VERSION,
                    semantic_class=semantic,
                    active=True,
                )
                self.session.add(row)
                self.session.flush()
            definitions[key] = row
        return definitions

    def observe(
        self,
        definition: MarketDefinition,
        effective_date: date,
        rights_policy: DataRightsPolicy,
    ) -> MarketObservation:
        if definition.tenant_id != rights_policy.tenant_id:
            raise ValueError("rights policy is outside the market tenant")
        _require_rights(rights_policy)
        members = self.session.scalars(
            select(MarketDefinitionMember).where(
                MarketDefinitionMember.market_definition_id == definition.id,
                MarketDefinitionMember.inclusion == MarketInclusion.INCLUDE,
                MarketDefinitionMember.member_type == MarketMemberType.TRACKED_QUERY,
            )
        ).all()
        if not members:
            raise ValueError("market definition has no supported tracked-query members")
        query_ids = [item.member_uuid for item in members if item.member_uuid]
        tracked = {
            item.id: item
            for item in self.session.scalars(
                select(TrackedQuery).where(
                    TrackedQuery.tenant_id == definition.tenant_id,
                    TrackedQuery.site_id == definition.site_id,
                    TrackedQuery.id.in_(query_ids),
                )
            ).all()
        }
        observations = self.session.scalars(
            select(SerpObservation).where(
                SerpObservation.tenant_id == definition.tenant_id,
                SerpObservation.site_id == definition.site_id,
                SerpObservation.tracked_query_id.in_(query_ids),
                SerpObservation.observed_date == effective_date,
                SerpObservation.effective_end.is_(None),
            )
        ).all()
        for policy_id in {item.rights_policy_id for item in observations}:
            upstream_policy = self.session.get(DataRightsPolicy, policy_id)
            if not upstream_policy:
                raise PermissionError("upstream SERP evidence has no rights policy")
            _require_rights(upstream_policy)
        observation_by_id = {item.id: item for item in observations}
        results = (
            self.session.scalars(
                select(SerpResult)
                .where(
                    SerpResult.serp_observation_id.in_(observation_by_id),
                    SerpResult.is_organic.is_(True),
                    SerpResult.rank_absolute <= 100,
                )
                .limit(MAX_RESULTS)
            ).all()
            if observation_by_id
            else []
        )
        return self._persist(
            definition, effective_date, rights_policy, tracked, observations, results
        )

    def _persist(
        self,
        definition: MarketDefinition,
        effective_date: date,
        rights_policy: DataRightsPolicy,
        tracked: dict[uuid.UUID, TrackedQuery],
        observations: Sequence[SerpObservation],
        results: Sequence[SerpResult],
    ) -> MarketObservation:
        observed_query_ids = {item.tracked_query_id for item in observations}
        status_value, coverage_rate = coverage_status(len(tracked), len(observed_query_ids))
        observation_lookup = {item.id: item for item in observations}
        participant: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "queries": set(),
                "pages": set(),
                "count": 0,
                "top3": 0,
                "top10": 0,
                "top20": 0,
                "weight": Decimal(0),
                "owned": False,
                "first": None,
                "last": None,
            }
        )
        query_domains: dict[uuid.UUID, set[str]] = defaultdict(set)
        query_weights: dict[uuid.UUID, dict[str, Decimal]] = defaultdict(
            lambda: defaultdict(Decimal)
        )
        for result in results:
            if not result.hostname:
                continue
            serp = observation_lookup[result.serp_observation_id]
            row = participant[result.hostname]
            row["queries"].add(serp.tracked_query_id)
            if result.normalized_url:
                row["pages"].add(result.normalized_url)
            row["count"] += 1
            row["top3"] += int(result.rank_absolute <= 3)
            row["top10"] += int(result.rank_absolute <= 10)
            row["top20"] += int(result.rank_absolute <= 20)
            weight = reciprocal_rank(result.rank_absolute)
            row["weight"] += weight
            row["owned"] = row["owned"] or result.ownership is ResultOwnership.OWN_SITE
            row["first"] = min(
                filter(None, (row["first"], serp.observed_at)), default=serp.observed_at
            )
            row["last"] = max(
                filter(None, (row["last"], serp.observed_at)), default=serp.observed_at
            )
            query_domains[serp.tracked_query_id].add(result.hostname)
            query_weights[serp.tracked_query_id][result.hostname] += weight

        normalized_queries = {row.normalized_query for row in tracked.values()}
        external_rows = self.session.execute(
            select(ExternalKeywordRanking, ExternalSearchObservation)
            .join(
                ExternalSearchObservation,
                ExternalSearchObservation.id
                == ExternalKeywordRanking.external_search_observation_id,
            )
            .where(
                ExternalSearchObservation.site_id == definition.site_id,
                ExternalSearchObservation.tenant_id == definition.tenant_id,
                ExternalSearchObservation.observed_date == effective_date,
                ExternalSearchObservation.effective_end.is_(None),
                country_scope(definition.country_code),
                ExternalSearchObservation.language_code == definition.language_code,
                ExternalSearchObservation.device == definition.device,
                ExternalKeywordRanking.normalized_keyword.in_(normalized_queries),
            )
            .limit(MAX_RESULTS)
        ).all()
        for _, external_observation in external_rows:
            upstream = self.session.get(DataRightsPolicy, external_observation.rights_policy_id)
            if not upstream:
                raise PermissionError("upstream external-search evidence has no rights policy")
            _require_rights(upstream)
        volume_weights: dict[str, Decimal] = defaultdict(Decimal)
        query_volume: dict[str, int] = {}
        for ranking, _ in external_rows:
            if ranking.search_volume is not None:
                query_volume[ranking.normalized_keyword] = max(
                    query_volume.get(ranking.normalized_keyword, 0), ranking.search_volume
                )
                volume_weights[ranking.ranking_domain] += Decimal(
                    ranking.search_volume
                ) * reciprocal_rank(ranking.position)

        visibility = shares({domain: row["weight"] for domain, row in participant.items()})
        volume_visibility = shares(volume_weights) if volume_weights else {}
        payload = {
            "definition_id": definition.id,
            "version": definition.version,
            "date": effective_date,
            "participants": {key: str(value) for key, value in sorted(visibility.items())},
            "volume_participants": {
                key: str(value) for key, value in sorted(volume_visibility.items())
            },
            "provider_query_volume": dict(sorted(query_volume.items())),
            "query_coverage": str(coverage_rate),
            "method": f"{METHOD_KEY}:{METHOD_VERSION}",
        }
        observation_key = _digest(
            [definition.id, effective_date, METHOD_KEY, METHOD_VERSION, definition.version]
        )
        content_hash = _digest(payload)
        current = self.session.scalar(
            select(MarketObservation).where(
                MarketObservation.observation_key == observation_key,
                MarketObservation.effective_end.is_(None),
            )
        )
        if current and current.content_hash == content_hash:
            return current
        now = datetime.now(timezone.utc)
        if current:
            current.effective_end = now
        market = MarketObservation(
            tenant_id=definition.tenant_id,
            organization_id=definition.organization_id,
            site_id=definition.site_id,
            market_definition_id=definition.id,
            market_definition_version=definition.version,
            rights_policy_id=rights_policy.id,
            rights_policy_version=rights_policy.policy_version,
            effective_date=effective_date,
            observed_at=datetime.combine(effective_date, time.min, timezone.utc),
            country_code=definition.country_code,
            language_code=definition.language_code,
            device=definition.device,
            method_key=METHOD_KEY,
            method_version=METHOD_VERSION,
            semantic_class=EventSemanticClass.GIS_DERIVED,
            coverage_status=MarketCoverageStatus(status_value),
            configured_query_count=len(tracked),
            observed_query_count=len(observed_query_ids),
            query_coverage_rate=coverage_rate,
            source_coverage={
                "serp_observations": len(observations),
                "serp_results": len(results),
                "external_rankings": len(external_rows),
            },
            observation_key=observation_key,
            content_hash=content_hash,
            provider_reported_cost=None,
            estimated_cost=Decimal(0),
            provenance_metadata={
                "source_policy_ids": sorted(str(item.rights_policy_id) for item in observations),
                "definition_frozen": True,
            },
            effective_start=now,
        )
        self.session.add(market)
        self.session.flush()
        for domain, row in participant.items():
            label, overlap = participant_class(
                row["owned"], len(row["queries"]), len(observed_query_ids)
            )
            self.session.add(
                MarketParticipantObservation(
                    market_observation_id=market.id,
                    domain=domain,
                    ownership="OWNED" if row["owned"] else "OTHER",
                    participant_class=MarketParticipantClass(label),
                    query_count=len(row["queries"]),
                    ranking_page_count=len(row["pages"]),
                    serp_appearance_count=row["count"],
                    top_3_appearances=row["top3"],
                    top_10_appearances=row["top10"],
                    top_20_appearances=row["top20"],
                    visibility_weight=row["weight"],
                    visibility_share=visibility[domain],
                    volume_weighted_visibility=volume_weights.get(domain),
                    volume_weighted_visibility_share=volume_visibility.get(domain),
                    query_overlap_rate=overlap,
                    first_observed_at=row["first"],
                    last_observed_at=row["last"],
                    classification_method=CLASSIFICATION_METHOD,
                    classification_version=CLASSIFICATION_VERSION,
                    semantic_class=EventSemanticClass.GIS_DERIVED,
                    metadata_json={
                        "visibility_method": METHOD_KEY,
                        "visibility_method_version": METHOD_VERSION,
                    },
                )
            )
        concentration = hhi(visibility.values())
        definitions = self.ensure_metric_definitions()
        metric_rows = (
            (
                "OBSERVED_QUERY_COUNT",
                Decimal(len(observed_query_ids)),
                "count",
                "gis",
                EventSemanticClass.MEASURED,
            ),
            (
                "OBSERVED_DOMAIN_COUNT",
                Decimal(len(participant)),
                "count",
                "gis",
                EventSemanticClass.MEASURED,
            ),
            ("MARKET_HHI", concentration, "ratio", "gis", EventSemanticClass.GIS_DERIVED),
            (
                "EFFECTIVE_COMPETITOR_COUNT",
                effective_competitor_count(concentration),
                "count",
                "gis",
                EventSemanticClass.GIS_DERIVED,
            ),
            (
                "TOTAL_PROVIDER_SEARCH_VOLUME",
                Decimal(sum(query_volume.values())) if query_volume else None,
                "searches",
                "external_search_provider",
                EventSemanticClass.PROVIDER_REPORTED,
            ),
            ("QUERY_COVERAGE_RATE", coverage_rate, "ratio", "gis", EventSemanticClass.GIS_DERIVED),
        )
        for key, value, unit, provider, semantic in metric_rows:
            self.session.add(
                MarketMetricObservation(
                    market_observation_id=market.id,
                    metric_definition_id=definitions[key].id,
                    metric_key=key,
                    metric_value=value,
                    unit=unit,
                    provider=provider,
                    method_key=METHOD_KEY
                    if key != "TOTAL_PROVIDER_SEARCH_VOLUME"
                    else "PROVIDER_REPORTED_SEARCH_VOLUME",
                    method_version=METHOD_VERSION,
                    semantic_class=semantic,
                    metadata_json={"no_data": value is None},
                )
            )
        segments: dict[str, set[uuid.UUID]] = defaultdict(set)
        for query_id in observed_query_ids:
            intent, _ = classify_intent(tracked[query_id].normalized_query)
            segments[intent].add(query_id)
        for intent, segment_queries in segments.items():
            domains = set().union(*(query_domains[item] for item in segment_queries))
            segment_domain_weights: dict[str, Decimal] = defaultdict(Decimal)
            for query_id in segment_queries:
                for domain, weight in query_weights[query_id].items():
                    segment_domain_weights[domain] += weight
            segment_shares = shares(segment_domain_weights)
            segment_volume = sum(
                (query_volume.get(tracked[item].normalized_query, 0) for item in segment_queries), 0
            )
            self.session.add(
                MarketSegmentObservation(
                    market_observation_id=market.id,
                    segment_type="SEARCH_INTENT",
                    segment_key=intent,
                    segment_label=intent.replace("_", " ").title(),
                    query_count=len(segment_queries),
                    participant_count=len(domains),
                    provider_reported_search_volume=Decimal(segment_volume)
                    if query_volume
                    else None,
                    observed_visibility_hhi=hhi(segment_shares.values())
                    if segment_shares
                    else None,
                    method_key="DETERMINISTIC_INTENT_RULES",
                    method_version="1.0.0",
                    semantic_class=EventSemanticClass.HEURISTIC,
                )
            )
        self.session.flush()
        return market
