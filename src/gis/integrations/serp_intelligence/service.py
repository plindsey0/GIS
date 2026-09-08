from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.integrations.serp.service import SerpCollector, SerpProvider, normalize_query
from gis.models import (
    AnalyticalEntity,
    CollectionTarget,
    CollectionTargetStatus,
    CollectionTargetType,
    CorroborationState,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    DemandEvidenceStrength,
    EvidenceCompatibility,
    EvidenceContract,
    EvidenceGap,
    EvidencePackage,
    EvidencePackageItem,
    EvidenceQualityDimension,
    EvidenceQualityRun,
    ExactQuerySerpSnapshotDetail,
    IngestionRun,
    IngestionStatus,
    MarketDefinition,
    PermittedUse,
    QualityDimensionState,
    QualityDimensionType,
    ResolutionStrength,
    ResultOwnership,
    RightsStatus,
    RightsUsability,
    SerpObservation,
    SerpResult,
    SourceIndependenceState,
    TrackedQuery,
)
from gis.provenance.service import assert_use_allowed, evaluate_policy_use

METHOD_VERSION = "EXACT_QUERY_SERP_V1"
TOP_RESULT_LIMIT = 20
PARTICIPANT_LIMIT = 10


class ExactQueryScopeError(ValueError):
    pass


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class _ScopeCheckingProvider:
    def __init__(self, delegate: SerpProvider, query: TrackedQuery) -> None:
        self.delegate = delegate
        self.query = query

    def collect(self, query: TrackedQuery) -> dict[str, Any]:
        payload = self.delegate.collect(query)
        tasks = payload.get("tasks") if isinstance(payload, dict) else None
        results = tasks[0].get("result") if isinstance(tasks, list) and tasks else None
        if isinstance(results, list) and results and isinstance(results[0], dict):
            result = results[0]
            checks = {
                "keyword": normalize_query(self.query.query_text),
                "country_code": self.query.country_code.upper(),
                "language_code": self.query.language_code.lower(),
                "device": self.query.device.lower(),
            }
            for key, expected in checks.items():
                supplied = result.get(key)
                if supplied is not None and str(supplied).strip().casefold() != expected.casefold():
                    raise ExactQueryScopeError(f"provider {key} does not match governed exact scope")
        return payload


class ExactQuerySerpService:
    """Adds governed scope, summaries, quality, and evidence to the existing SERP collector."""

    def __init__(self, session: Session, provider: SerpProvider) -> None:
        self.session = session
        self.provider = provider

    def collect(
        self,
        connection_id: uuid.UUID,
        tracked_query_id: uuid.UUID,
        collection_target_id: uuid.UUID,
        analytical_entity_id: uuid.UUID,
    ) -> IngestionRun:
        query = self.session.get(TrackedQuery, tracked_query_id)
        target = self.session.get(CollectionTarget, collection_target_id)
        entity = self.session.get(AnalyticalEntity, analytical_entity_id)
        if not query or not target or not entity:
            raise ExactQueryScopeError("query, target, and analytical entity are required")
        if not (
            query.tenant_id == target.tenant_id == entity.tenant_id
            and query.site_id == target.site_id == entity.site_id
        ):
            raise ExactQueryScopeError("query, target, and entity tenant/site scope mismatch")
        if target.target_type is not CollectionTargetType.QUERY:
            raise ExactQueryScopeError("exact-query SERP collection requires a query target")
        if target.status is not CollectionTargetStatus.ACTIVE:
            raise ExactQueryScopeError("collection target is not in an applied active plan")
        if normalize_query(target.display_value) != query.normalized_query:
            raise ExactQueryScopeError("collection target is not the governed exact query")
        if normalize_query(entity.canonical_key) != query.normalized_query:
            raise ExactQueryScopeError("analytical entity is not the governed exact query")
        market = self.session.get(MarketDefinition, target.market_definition_id)
        if not market or (
            market.country_code != query.country_code
            or market.language_code != query.language_code
            or market.device != query.device
        ):
            raise ExactQueryScopeError("market and tracked-query scope mismatch")
        connection = self.session.get(DataSourceConnection, connection_id)
        if not connection or connection.tenant_id != query.tenant_id:
            raise ExactQueryScopeError("provider connection is outside governed scope")
        policy = self.session.get(DataRightsPolicy, connection.rights_policy_id)
        if not policy:
            source = self.session.get(DataSource, connection.data_source_id)
            policy = self.session.get(DataRightsPolicy, source.default_rights_policy_id) if source else None
        if not policy:
            raise ExactQueryScopeError("SERP rights policy is required")
        assert_use_allowed(evaluate_policy_use(self.session, policy, PermittedUse.NORMALIZED_RETENTION))

        run = SerpCollector(
            self.session, _ScopeCheckingProvider(self.provider, query)
        ).sync(connection_id, query)
        if run.status is not IngestionStatus.SUCCEEDED:
            return run
        observation_id = run.source_metadata.get("reused_observation_id")
        observation = (
            self.session.get(SerpObservation, uuid.UUID(str(observation_id)))
            if observation_id
            else self.session.scalar(select(SerpObservation).where(
                SerpObservation.ingestion_run_id == run.id
            ))
        )
        existing_detail = self.session.scalar(select(ExactQuerySerpSnapshotDetail).where(
            ExactQuerySerpSnapshotDetail.observation_id == observation.id
        )) if observation else None
        if not observation or existing_detail:
            return run
        detail = self._detail(observation, target, entity, market)
        self.session.add(detail)
        self.session.flush()
        detail.evidence_package_id = self._package(detail, observation, policy).id
        self.session.commit()
        return run

    def _detail(
        self,
        observation: SerpObservation,
        target: CollectionTarget,
        entity: AnalyticalEntity,
        market: MarketDefinition,
    ) -> ExactQuerySerpSnapshotDetail:
        results = list(self.session.scalars(select(SerpResult).where(
            SerpResult.serp_observation_id == observation.id
        ).order_by(SerpResult.rank_absolute, SerpResult.id)))
        previous = self.session.scalar(select(ExactQuerySerpSnapshotDetail).where(
            ExactQuerySerpSnapshotDetail.analytical_entity_id == entity.id
        ).order_by(ExactQuerySerpSnapshotDetail.observed_at.desc(),
                   ExactQuerySerpSnapshotDetail.created_at.desc()).limit(1))
        owned = [row for row in results if row.ownership is ResultOwnership.OWN_SITE]
        returned_depth = max((row.rank_absolute for row in results), default=0)
        normalized = [
            [row.rank_absolute, row.provider_type, row.normalized_url, row.hostname, row.title]
            for row in results
        ]
        snapshot_hash = _hash(normalized)
        limitations = []
        if returned_depth < observation.requested_depth:
            limitations.append(
                f"Requested depth {observation.requested_depth}; observed depth {returned_depth}."
            )
        if not results:
            limitations.append("Provider returned no valid normalized SERP results.")
        if not any(row.is_feature for row in results):
            limitations.append("No SERP feature data was observed; absence may reflect provider coverage.")
        limitations.extend([
            "Observed SERP participant does not establish a business competitor.",
            "Observed query-page result does not establish intent satisfaction.",
            "A site not observed within collected depth must not be described as not ranking.",
        ])
        summary = self._summary(results, observation.requested_depth)
        comparison = self._comparison(previous, results, observation) if previous else {
            "state": "INSUFFICIENT_HISTORY"
        }
        quality = "USABLE_LIMITED" if results else "INSUFFICIENT"
        return ExactQuerySerpSnapshotDetail(
            observation_id=observation.id,
            tenant_id=observation.tenant_id,
            site_id=observation.site_id,
            analytical_entity_id=entity.id,
            collection_target_id=target.id,
            market_definition_id=market.id,
            previous_observation_id=previous.observation_id if previous else None,
            observed_at=observation.observed_at,
            provider="dataforseo",
            method_version=METHOD_VERSION,
            returned_depth=returned_depth,
            result_count=len(results),
            snapshot_hash=snapshot_hash,
            change_classification=(
                "FIRST_OBSERVATION" if not previous else
                "UNCHANGED_RECOLLECTION" if previous.snapshot_hash == snapshot_hash else
                "CHANGED"
            ),
            owned_presence_state=(
                "OBSERVED_WITHIN_COLLECTED_DEPTH" if owned
                else "NOT_OBSERVED_WITHIN_COLLECTED_DEPTH"
            ),
            owned_best_position=min((row.rank_absolute for row in owned), default=None),
            summary_json=summary,
            comparison_json=comparison,
            quality_state=quality,
            limitations_json=limitations,
            reassessment_ready=bool(results),
        )

    @staticmethod
    def _summary(results: list[SerpResult], requested_depth: int) -> dict[str, Any]:
        domains: dict[str, list[SerpResult]] = defaultdict(list)
        for row in results:
            if row.hostname:
                domains[row.hostname].append(row)
        types = Counter(row.feature_type.value for row in results)
        repeated = sum(len(rows) for rows in domains.values() if len(rows) > 1)
        owned = [row for row in results if row.ownership is ResultOwnership.OWN_SITE]
        top_results = [row for row in results if row.rank_absolute <= TOP_RESULT_LIMIT]
        for row in owned:
            if row not in top_results:
                top_results.append(row)
        return {
            "requested_depth": requested_depth,
            "result_count": len(results),
            "unique_domains": len(domains),
            "unique_domains_top_10": len({r.hostname for r in results if r.rank_absolute <= 10 and r.hostname}),
            "unique_domains_top_20": len({r.hostname for r in results if r.rank_absolute <= 20 and r.hostname}),
            "repeated_domain_result_share": repeated / len(results) if results else 0,
            "result_type_counts": dict(sorted(types.items())),
            "top_domains": [
                {"domain": domain, "result_count": len(rows),
                 "best_position": min(row.rank_absolute for row in rows),
                 "urls": [row.normalized_url for row in rows if row.normalized_url][:5],
                 "result_types": sorted({row.feature_type.value for row in rows})}
                for domain, rows in sorted(domains.items(), key=lambda item: (
                    min(row.rank_absolute for row in item[1]), item[0]
                ))[:PARTICIPANT_LIMIT]
            ],
            "owned_results": [
                {"result_id": str(row.id), "position": row.rank_absolute,
                 "url": row.normalized_url, "result_type": row.feature_type.value}
                for row in owned
            ],
            "top_results": [
                {"result_id": str(row.id), "position": row.rank_absolute,
                 "type": row.feature_type.value, "provider_type": row.provider_type,
                 "domain": row.hostname, "url": row.normalized_url,
                 "title": row.title, "snippet": row.snippet,
                 "owned": row.ownership is ResultOwnership.OWN_SITE,
                 "title_contains_calculator": "calculator" in (row.title or "").casefold(),
                 "url_contains_calculator": "calculator" in (row.normalized_url or "").casefold(),
                 "gov_domain": bool(row.hostname and row.hostname.endswith(".gov"))}
                for row in sorted(top_results, key=lambda item: item.rank_absolute)
            ],
        }

    def _comparison(
        self,
        previous: ExactQuerySerpSnapshotDetail,
        current_results: list[SerpResult],
        current: SerpObservation,
    ) -> dict[str, Any]:
        prior_results = list(self.session.scalars(select(SerpResult).where(
            SerpResult.serp_observation_id == previous.observation_id
        )))
        old = {row.normalized_url: row for row in prior_results if row.normalized_url}
        new = {row.normalized_url: row for row in current_results if row.normalized_url}
        movements = [
            {"url": url, "previous_position": old[url].rank_absolute,
             "current_position": new[url].rank_absolute,
             "direction": "INCREASED" if new[url].rank_absolute < old[url].rank_absolute
             else "DECREASED" if new[url].rank_absolute > old[url].rank_absolute else "UNCHANGED"}
            for url in sorted(old.keys() & new.keys())
        ]
        old_features = {row.feature_type.value for row in prior_results if row.is_feature}
        new_features = {row.feature_type.value for row in current_results if row.is_feature}
        return {
            "state": "COMPARABLE",
            "previous_observation_id": str(previous.observation_id),
            "previous_observed_at": previous.observed_at.isoformat(),
            "current_observed_at": current.observed_at.isoformat(),
            "previous_depth": previous.returned_depth,
            "current_depth": max((row.rank_absolute for row in current_results), default=0),
            "entered_urls": sorted(new.keys() - old.keys())[:20],
            "exited_urls": sorted(old.keys() - new.keys())[:20],
            "position_movements": movements[:20],
            "domains_entered": sorted({r.hostname for r in current_results if r.hostname} -
                                      {r.hostname for r in prior_results if r.hostname})[:20],
            "domains_exited": sorted({r.hostname for r in prior_results if r.hostname} -
                                     {r.hostname for r in current_results if r.hostname})[:20],
            "features_appeared": sorted(new_features - old_features),
            "features_disappeared": sorted(old_features - new_features),
            "owned_position_previous": previous.owned_best_position,
            "owned_position_current": min((r.rank_absolute for r in current_results
                                            if r.ownership is ResultOwnership.OWN_SITE), default=None),
        }

    def _package(
        self,
        detail: ExactQuerySerpSnapshotDetail,
        observation: SerpObservation,
        policy: DataRightsPolicy,
    ) -> EvidencePackage:
        contract = self.session.scalar(select(EvidenceContract).where(
            EvidenceContract.contract_key == "EXACT_QUERY_SERP",
            EvidenceContract.contract_version == METHOD_VERSION,
        ))
        if not contract:
            contract = EvidenceContract(
                contract_key="EXACT_QUERY_SERP", contract_version=METHOD_VERSION,
                description="Governed point-in-time exact-query SERP observation.",
                requirements_json={"exact_query": True, "market_scope": True,
                                   "does_not_assert_intent": True},
            )
            self.session.add(contract)
            self.session.flush()
        quality_run = EvidenceQualityRun(
            tenant_id=observation.tenant_id, site_id=observation.site_id,
            method_version=METHOD_VERSION, assessed_at=datetime.now(timezone.utc),
            fingerprint=_hash([observation.id, METHOD_VERSION]), input_count=1,
            package_count=1,
            metadata_json={"provider_observations": 1, "root_source": "dataforseo"},
        )
        self.session.add(quality_run)
        self.session.flush()
        rights_status = evaluate_policy_use(
            self.session, policy, PermittedUse.DERIVATIVE_CREATION
        ).status
        rights = RightsUsability.USABLE if rights_status is RightsStatus.ALLOWED else (
            RightsUsability.BLOCKED if rights_status is RightsStatus.DENIED else RightsUsability.UNKNOWN
        )
        if rights is not RightsUsability.USABLE:
            detail.reassessment_ready = False
            detail.limitations_json = [*detail.limitations_json,
                                       "Rights do not authorize derivative evidence use."]
        package = EvidencePackage(
            quality_run_id=quality_run.id, tenant_id=observation.tenant_id,
            site_id=observation.site_id, analytical_entity_id=detail.analytical_entity_id,
            evidence_contract_id=contract.id, market_definition_id=detail.market_definition_id,
            condition_key="EXACT_QUERY_SERP_COMPETITOR_EVIDENCE",
            classification="EXACT_QUERY_SERP_OBSERVED", period_start=observation.observed_date,
            period_end=observation.observed_date,
            sufficiency=(DemandEvidenceStrength.LIMITED if detail.result_count
                         else DemandEvidenceStrength.INSUFFICIENT),
            identity_resolution=ResolutionStrength.EXACT,
            source_independence=SourceIndependenceState.SAME_ROOT_SOURCE,
            corroboration=CorroborationState.SINGLE_SOURCE, rights_usability=rights,
            conflict_count=0, independent_source_count=1,
            limitations_json=detail.limitations_json,
            identity_hash=_hash([observation.id, contract.id, detail.analytical_entity_id]),
            method_version=METHOD_VERSION,
        )
        self.session.add(package)
        self.session.flush()
        states = {
            QualityDimensionType.IDENTITY_RESOLUTION: QualityDimensionState.STRONG,
            QualityDimensionType.FRESHNESS: QualityDimensionState.SUPPORTED,
            QualityDimensionType.COMPLETENESS: (QualityDimensionState.SUPPORTED
                if detail.returned_depth >= observation.requested_depth else QualityDimensionState.LIMITED),
            QualityDimensionType.PROVENANCE_COMPLETENESS: QualityDimensionState.SUPPORTED,
            QualityDimensionType.METHOD_COMPATIBILITY: QualityDimensionState.SUPPORTED,
            QualityDimensionType.SCOPE_COMPATIBILITY: QualityDimensionState.SUPPORTED,
            QualityDimensionType.RIGHTS_USABILITY: (QualityDimensionState.SUPPORTED
                if rights is RightsUsability.USABLE else QualityDimensionState.BLOCKED),
            QualityDimensionType.TEMPORAL_CONTINUITY: (QualityDimensionState.SUPPORTED
                if detail.previous_observation_id else QualityDimensionState.UNKNOWN),
        }
        for dimension, state in states.items():
            self.session.add(EvidenceQualityDimension(
                evidence_package_id=package.id, dimension=dimension, state=state,
                method_key=f"EXACT_SERP_{dimension.value}_V1", method_version=METHOD_VERSION,
                reasons_json=["Deterministic exact-query SERP assessment."],
            ))
        self.session.add(EvidencePackageItem(
            evidence_package_id=package.id, evidence_key=str(observation.id),
            evidence_type="EXACT_QUERY_SERP_SNAPSHOT", evidence_reference_id=observation.id,
            evidence_role="EXACT_QUERY_SEARCH_ENVIRONMENT", root_source_key="dataforseo",
            independence=SourceIndependenceState.SAME_ROOT_SOURCE,
            method_compatibility=EvidenceCompatibility.COMPATIBLE,
            scope_compatibility=EvidenceCompatibility.COMPATIBLE, rights_usability=rights,
            supports_claim=rights is RightsUsability.USABLE,
            metadata_json={"query": observation.normalized_query,
                           "returned_depth": detail.returned_depth},
        ))
        gaps = self.session.scalars(select(EvidenceGap).where(
            EvidenceGap.collection_target_id == detail.collection_target_id,
            EvidenceGap.gap_type == "EXACT_QUERY_SERP_COMPETITOR_EVIDENCE",
            EvidenceGap.resolved_at.is_(None),
        )).all()
        for gap in gaps if detail.reassessment_ready else []:
            gap.provenance_metadata = {
                **gap.provenance_metadata, "reassessment_ready": True,
                "candidate_evidence_package_id": str(package.id),
                "candidate_serp_observation_id": str(observation.id),
            }
        return package
