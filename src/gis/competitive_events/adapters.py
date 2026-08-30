from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.competitive_events.policy import decimal_thresholds
from gis.competitive_events.rules import (
    experience_change,
    material_numeric_change,
    rank_change,
    set_changes,
)
from gis.competitive_events.service import EventCandidate, EvidenceRef
from gis.models import (
    AuthorityLinkState,
    AuthorityMetricObservation,
    AuthorityObservation,
    BacklinkObservation,
    CompetitiveContentComponent,
    CompetitiveContentDocument,
    CompetitiveContentHeading,
    CompetitiveContentObservation,
    CompetitiveContentSchemaType,
    CompetitiveEventDomain,
    CompetitiveEventType,
    CompetitiveSubjectType,
    EventSemanticClass,
    EvidenceRole,
    ExperienceAvailability,
    ExperienceObservation,
    ExternalKeywordRanking,
    ExternalSearchObservation,
    ReferringDomainObservation,
    SerpObservation,
    SerpResult,
    TechnologyDetection,
    TechnologyObservation,
)


def evidence(
    observation: Any,
    asset: str,
    role: EvidenceRole,
    *,
    confidence: Decimal = Decimal("1"),
    semantic: EventSemanticClass = EventSemanticClass.MEASURED,
) -> EvidenceRef:
    return EvidenceRef(
        asset,
        str(observation.id),
        observation.observed_at,
        role,
        semantic,
        confidence,
        observation.data_source_connection_id,
        observation.ingestion_run_id,
        observation.rights_policy_id,
        observation.rights_policy_version,
    )


def pair_evidence(
    before: Any, after: Any, asset: str, **kwargs: Any
) -> tuple[EvidenceRef, EvidenceRef]:
    return (
        evidence(before, asset, EvidenceRole.BEFORE, **kwargs),
        evidence(after, asset, EvidenceRole.AFTER, **kwargs),
    )


def _ordered_pairs(items: list[Any]) -> list[tuple[Any | None, Any]]:
    return [(items[index - 1] if index else None, item) for index, item in enumerate(items)]


def synthesize_serp(
    session: Session,
    tenant_id: Any,
    site_id: Any,
    start: datetime,
    end: datetime,
    thresholds: dict[str, Any],
) -> list[EventCandidate]:
    observations = session.scalars(
        select(SerpObservation)
        .where(
            SerpObservation.tenant_id == tenant_id,
            SerpObservation.site_id == site_id,
            SerpObservation.observed_at <= end,
        )
        .order_by(SerpObservation.tracked_query_id, SerpObservation.observed_at)
    ).all()
    grouped: dict[Any, list[SerpObservation]] = defaultdict(list)
    for item in observations:
        grouped[item.tracked_query_id].append(item)
    candidates: list[EventCandidate] = []
    for items in grouped.values():
        for before, after in _ordered_pairs(items):
            if before is None or after.observed_at < start:
                continue
            before_results = session.scalars(
                select(SerpResult).where(SerpResult.serp_observation_id == before.id)
            ).all()
            after_results = session.scalars(
                select(SerpResult).where(SerpResult.serp_observation_id == after.id)
            ).all()

            def key(row: SerpResult) -> str:
                return row.normalized_url or (
                    f"{row.hostname or ''}|{row.feature_type.value}|{row.provider_type}"
                )

            old = {key(row): row for row in before_results}
            new = {key(row): row for row in after_results}
            for subject in sorted(set(old) | set(new)):
                change = rank_change(
                    subject,
                    old[subject].rank_absolute if subject in old else None,
                    new[subject].rank_absolute if subject in new else None,
                    minimum=int(thresholds["rank_movement_min"]),
                    thresholds=list(thresholds["rank_thresholds"]),
                )
                if change:
                    row = new.get(subject) or old[subject]
                    candidates.append(
                        EventCandidate(
                            CompetitiveSubjectType.PAGE,
                            subject,
                            CompetitiveEventDomain.SERP,
                            change.event_type,
                            after.observed_at,
                            pair_evidence(
                                before,
                                after,
                                "gis_raw.serp_observation",
                                semantic=EventSemanticClass.PROVIDER_REPORTED,
                            ),
                            EventSemanticClass.GIS_DERIVED,
                            subject_domain=row.hostname,
                            subject_url=row.normalized_url,
                            magnitude=change.magnitude,
                            magnitude_unit=change.unit,
                            metadata={
                                "query": after.normalized_query,
                                "before_rank": old[subject].rank_absolute
                                if subject in old
                                else None,
                                "after_rank": new[subject].rank_absolute
                                if subject in new
                                else None,
                            },
                        )
                    )
            old_features = {key(row): row for row in before_results if row.is_feature}
            new_features = {key(row): row for row in after_results if row.is_feature}
            for change in set_changes(
                set(old_features),
                set(new_features),
                CompetitiveEventType.SERP_FEATURE_APPEARED,
                CompetitiveEventType.SERP_FEATURE_DISAPPEARED,
            ):
                row = new_features.get(change.subject_key) or old_features[change.subject_key]
                candidates.append(
                    EventCandidate(
                        CompetitiveSubjectType.SERP_FEATURE,
                        change.subject_key,
                        CompetitiveEventDomain.SERP,
                        change.event_type,
                        after.observed_at,
                        pair_evidence(
                            before,
                            after,
                            "gis_raw.serp_observation",
                            semantic=EventSemanticClass.PROVIDER_REPORTED,
                        ),
                        subject_domain=row.hostname,
                        subject_url=row.normalized_url,
                        event_subtype=row.feature_type.value,
                        metadata={"query": after.normalized_query},
                    )
                )
    return candidates


def synthesize_search(
    session: Session,
    tenant_id: Any,
    site_id: Any,
    start: datetime,
    end: datetime,
    thresholds: dict[str, Any],
) -> list[EventCandidate]:
    observations = session.scalars(
        select(ExternalSearchObservation)
        .where(
            ExternalSearchObservation.tenant_id == tenant_id,
            ExternalSearchObservation.site_id == site_id,
            ExternalSearchObservation.observed_at <= end,
        )
        .order_by(
            ExternalSearchObservation.target_domain,
            ExternalSearchObservation.observation_type,
            ExternalSearchObservation.observed_at,
        )
    ).all()
    grouped: dict[tuple[str, str], list[ExternalSearchObservation]] = defaultdict(list)
    for item in observations:
        grouped[(item.target_domain, item.observation_type)].append(item)
    candidates: list[EventCandidate] = []
    for items in grouped.values():
        for before, after in _ordered_pairs(items):
            if before is None or after.observed_at < start:
                continue
            old_rows = session.scalars(
                select(ExternalKeywordRanking).where(
                    ExternalKeywordRanking.external_search_observation_id == before.id
                )
            ).all()
            new_rows = session.scalars(
                select(ExternalKeywordRanking).where(
                    ExternalKeywordRanking.external_search_observation_id == after.id
                )
            ).all()
            old = {row.normalized_keyword for row in old_rows}
            new = {row.normalized_keyword for row in new_rows}
            for change in set_changes(
                old, new, CompetitiveEventType.KEYWORD_GAINED, CompetitiveEventType.KEYWORD_LOST
            ):
                candidates.append(
                    EventCandidate(
                        CompetitiveSubjectType.QUERY,
                        change.subject_key,
                        CompetitiveEventDomain.SEARCH_VISIBILITY,
                        change.event_type,
                        after.observed_at,
                        pair_evidence(
                            before,
                            after,
                            "gis_raw.external_search_observation",
                            semantic=EventSemanticClass.PROVIDER_REPORTED,
                        ),
                        EventSemanticClass.GIS_DERIVED,
                        subject_domain=after.target_domain,
                    )
                )
            old_visibility = sum(
                (row.estimated_traffic_share or Decimal("0") for row in old_rows), Decimal("0")
            )
            new_visibility = sum(
                (row.estimated_traffic_share or Decimal("0") for row in new_rows), Decimal("0")
            )
            visibility_change = material_numeric_change(
                after.target_domain,
                old_visibility,
                new_visibility,
                absolute_min=thresholds["visibility_absolute_min"],
                percent_min=thresholds["visibility_percent_min"],
                increased=CompetitiveEventType.SEARCH_VISIBILITY_INCREASED,
                decreased=CompetitiveEventType.SEARCH_VISIBILITY_DECREASED,
                unit="estimated_traffic_share",
            )
            if visibility_change:
                candidates.append(
                    EventCandidate(
                        CompetitiveSubjectType.DOMAIN,
                        after.target_domain,
                        CompetitiveEventDomain.SEARCH_VISIBILITY,
                        visibility_change.event_type,
                        after.observed_at,
                        pair_evidence(
                            before,
                            after,
                            "gis_raw.external_search_observation",
                            semantic=EventSemanticClass.PROVIDER_REPORTED,
                        ),
                        EventSemanticClass.GIS_DERIVED,
                        subject_domain=after.target_domain,
                        magnitude=visibility_change.magnitude,
                        magnitude_unit=visibility_change.unit,
                    )
                )
    return candidates


def synthesize_content(
    session: Session,
    tenant_id: Any,
    site_id: Any,
    start: datetime,
    end: datetime,
    thresholds: dict[str, Any],
) -> list[EventCandidate]:
    observations = session.scalars(
        select(CompetitiveContentObservation)
        .where(
            CompetitiveContentObservation.tenant_id == tenant_id,
            CompetitiveContentObservation.site_id == site_id,
            CompetitiveContentObservation.observed_at <= end,
        )
        .order_by(
            CompetitiveContentObservation.normalized_url, CompetitiveContentObservation.observed_at
        )
    ).all()
    grouped: dict[str, list[CompetitiveContentObservation]] = defaultdict(list)
    for item in observations:
        grouped[item.normalized_url].append(item)
    candidates: list[EventCandidate] = []
    for url, items in grouped.items():
        for before, after in _ordered_pairs(items):
            if after.observed_at < start:
                continue
            ev = (
                (evidence(after, "gis_raw.competitive_content_observation", EvidenceRole.PRIMARY),)
                if before is None
                else pair_evidence(before, after, "gis_raw.competitive_content_observation")
            )
            if before is None:
                candidates.append(
                    EventCandidate(
                        CompetitiveSubjectType.PAGE,
                        url,
                        CompetitiveEventDomain.CONTENT,
                        CompetitiveEventType.PAGE_FIRST_OBSERVED,
                        after.observed_at,
                        ev,
                        subject_domain=after.domain,
                        subject_url=url,
                    )
                )
                continue
            if (
                before.content_hash
                and after.content_hash
                and before.content_hash != after.content_hash
            ):
                candidates.append(
                    EventCandidate(
                        CompetitiveSubjectType.PAGE,
                        url,
                        CompetitiveEventDomain.CONTENT,
                        CompetitiveEventType.PAGE_CONTENT_CHANGED,
                        after.observed_at,
                        ev,
                        subject_domain=after.domain,
                        subject_url=url,
                    )
                )
            old_doc = session.get(CompetitiveContentDocument, before.id)
            new_doc = session.get(CompetitiveContentDocument, after.id)
            if old_doc and new_doc:
                for field, kind in (
                    ("title", CompetitiveEventType.TITLE_CHANGED),
                    ("meta_description", CompetitiveEventType.META_DESCRIPTION_CHANGED),
                ):
                    if getattr(old_doc, field) != getattr(new_doc, field):
                        candidates.append(
                            EventCandidate(
                                CompetitiveSubjectType.PAGE,
                                url,
                                CompetitiveEventDomain.CONTENT,
                                kind,
                                after.observed_at,
                                ev,
                                subject_domain=after.domain,
                                subject_url=url,
                                metadata={"field": field},
                            )
                        )
                word_change = material_numeric_change(
                    url,
                    Decimal(old_doc.normalized_word_count),
                    Decimal(new_doc.normalized_word_count),
                    absolute_min=Decimal(thresholds["word_count_absolute_min"]),
                    percent_min=thresholds["word_count_percent_min"],
                    increased=CompetitiveEventType.WORD_COUNT_INCREASED,
                    decreased=CompetitiveEventType.WORD_COUNT_DECREASED,
                    unit="words",
                )
                if word_change:
                    candidates.append(
                        EventCandidate(
                            CompetitiveSubjectType.PAGE,
                            url,
                            CompetitiveEventDomain.CONTENT,
                            word_change.event_type,
                            after.observed_at,
                            ev,
                            subject_domain=after.domain,
                            subject_url=url,
                            magnitude=word_change.magnitude,
                            magnitude_unit=word_change.unit,
                        )
                    )
            old_headings = session.scalars(
                select(CompetitiveContentHeading)
                .where(CompetitiveContentHeading.observation_id == before.id)
                .order_by(CompetitiveContentHeading.ordinal)
            ).all()
            new_headings = session.scalars(
                select(CompetitiveContentHeading)
                .where(CompetitiveContentHeading.observation_id == after.id)
                .order_by(CompetitiveContentHeading.ordinal)
            ).all()
            if [(row.level, row.normalized_text) for row in old_headings] != [
                (row.level, row.normalized_text) for row in new_headings
            ]:
                candidates.append(
                    EventCandidate(
                        CompetitiveSubjectType.PAGE,
                        url,
                        CompetitiveEventDomain.CONTENT,
                        CompetitiveEventType.HEADING_STRUCTURE_CHANGED,
                        after.observed_at,
                        ev,
                        subject_domain=after.domain,
                        subject_url=url,
                    )
                )
            for model, attr, kind in (
                (
                    CompetitiveContentComponent,
                    "component_type",
                    CompetitiveEventType.CONTENT_COMPONENT_APPEARED,
                ),
                (
                    CompetitiveContentSchemaType,
                    "schema_type",
                    CompetitiveEventType.SCHEMA_TYPE_APPEARED,
                ),
            ):
                old_set = {
                    getattr(row, attr)
                    for row in session.scalars(
                        select(model).where(model.observation_id == before.id)
                    ).all()
                }
                new_set = {
                    getattr(row, attr)
                    for row in session.scalars(
                        select(model).where(model.observation_id == after.id)
                    ).all()
                }
                for item in sorted(new_set - old_set):
                    candidates.append(
                        EventCandidate(
                            CompetitiveSubjectType.CONTENT_COMPONENT,
                            f"{url}|{item}",
                            CompetitiveEventDomain.CONTENT,
                            kind,
                            after.observed_at,
                            ev,
                            subject_domain=after.domain,
                            subject_url=url,
                            event_subtype=item,
                        )
                    )
    return candidates


def synthesize_technology(
    session: Session,
    tenant_id: Any,
    site_id: Any,
    start: datetime,
    end: datetime,
    thresholds: dict[str, Any],
) -> list[EventCandidate]:
    del thresholds
    observations = session.scalars(
        select(TechnologyObservation)
        .where(
            TechnologyObservation.tenant_id == tenant_id,
            TechnologyObservation.site_id == site_id,
            TechnologyObservation.observed_at <= end,
        )
        .order_by(TechnologyObservation.normalized_url, TechnologyObservation.observed_at)
    ).all()
    grouped: dict[str, list[TechnologyObservation]] = defaultdict(list)
    for item in observations:
        grouped[item.normalized_url].append(item)
    candidates: list[EventCandidate] = []
    for url, items in grouped.items():
        for before, after in _ordered_pairs(items):
            if after.observed_at < start:
                continue
            old_rows = (
                []
                if before is None
                else session.scalars(
                    select(TechnologyDetection).where(
                        TechnologyDetection.observation_id == before.id,
                        TechnologyDetection.presence_status == "PRESENT",
                    )
                ).all()
            )
            new_rows = session.scalars(
                select(TechnologyDetection).where(
                    TechnologyDetection.observation_id == after.id,
                    TechnologyDetection.presence_status == "PRESENT",
                )
            ).all()
            old = {row.technology_id: row for row in old_rows}
            new = {row.technology_id: row for row in new_rows}
            ev = (
                (evidence(after, "gis_raw.technology_observation", EvidenceRole.PRIMARY),)
                if before is None
                else pair_evidence(before, after, "gis_raw.technology_observation")
            )
            for technology_id, row in new.items():
                if technology_id not in old:
                    kind = (
                        CompetitiveEventType.TECHNOLOGY_FIRST_DETECTED
                        if before is None
                        else CompetitiveEventType.TECHNOLOGY_ADDED
                    )
                    candidates.append(
                        EventCandidate(
                            CompetitiveSubjectType.TECHNOLOGY,
                            str(technology_id),
                            CompetitiveEventDomain.TECHNOLOGY,
                            kind,
                            after.observed_at,
                            ev,
                            EventSemanticClass.GIS_DERIVED,
                            row.confidence,
                            subject_id=technology_id,
                            subject_domain=after.domain,
                            subject_url=url,
                        )
                    )
                elif (
                    row.detected_version
                    and row.detected_version != old[technology_id].detected_version
                ):
                    candidates.append(
                        EventCandidate(
                            CompetitiveSubjectType.TECHNOLOGY,
                            str(technology_id),
                            CompetitiveEventDomain.TECHNOLOGY,
                            CompetitiveEventType.TECHNOLOGY_VERSION_CHANGED,
                            after.observed_at,
                            ev,
                            EventSemanticClass.GIS_DERIVED,
                            min(row.confidence, old[technology_id].confidence),
                            subject_id=technology_id,
                            subject_domain=after.domain,
                            subject_url=url,
                            metadata={
                                "before_version": old[technology_id].detected_version,
                                "after_version": row.detected_version,
                            },
                        )
                    )
            # Absence from `new` is deliberately ignored; non-detection is not removal evidence.
    return candidates


def synthesize_experience(
    session: Session,
    tenant_id: Any,
    site_id: Any,
    start: datetime,
    end: datetime,
    thresholds: dict[str, Any],
) -> list[EventCandidate]:
    observations = session.scalars(
        select(ExperienceObservation)
        .where(
            ExperienceObservation.tenant_id == tenant_id,
            ExperienceObservation.site_id == site_id,
            ExperienceObservation.observed_at <= end,
            ExperienceObservation.availability == ExperienceAvailability.DATA_AVAILABLE,
        )
        .order_by(
            ExperienceObservation.normalized_target,
            ExperienceObservation.metric,
            ExperienceObservation.form_factor,
            ExperienceObservation.observed_at,
        )
    ).all()
    grouped: dict[tuple[str, Any, Any], list[ExperienceObservation]] = defaultdict(list)
    for item in observations:
        grouped[(item.normalized_target, item.metric, item.form_factor)].append(item)
    candidates: list[EventCandidate] = []
    for items in grouped.values():
        for before, after in _ordered_pairs(items):
            if (
                before is None
                or after.observed_at < start
                or before.metric_value is None
                or after.metric_value is None
            ):
                continue
            change = experience_change(
                f"{after.normalized_target}|{after.metric.value}|{after.form_factor.value}",
                after.metric,
                before.metric_value,
                after.metric_value,
                thresholds["experience_absolute"][after.metric.value],
            )
            if change:
                candidates.append(
                    EventCandidate(
                        CompetitiveSubjectType.PAGE,
                        change.subject_key,
                        CompetitiveEventDomain.EXPERIENCE,
                        change.event_type,
                        after.observed_at,
                        pair_evidence(
                            before,
                            after,
                            "gis_raw.experience_observation",
                            semantic=EventSemanticClass.MEASURED,
                        ),
                        EventSemanticClass.GIS_DERIVED,
                        subject_url=after.normalized_target,
                        event_subtype=after.metric.value,
                        magnitude=change.magnitude,
                        magnitude_unit=after.unit,
                    )
                )
    return candidates


def synthesize_authority(
    session: Session,
    tenant_id: Any,
    site_id: Any,
    start: datetime,
    end: datetime,
    thresholds: dict[str, Any],
) -> list[EventCandidate]:
    observations = session.scalars(
        select(AuthorityObservation)
        .where(
            AuthorityObservation.tenant_id == tenant_id,
            AuthorityObservation.site_id == site_id,
            AuthorityObservation.observed_at <= end,
        )
        .order_by(
            AuthorityObservation.provider,
            AuthorityObservation.target_domain,
            AuthorityObservation.target_url,
            AuthorityObservation.observed_at,
        )
    ).all()
    candidates: list[EventCandidate] = []
    seen_links: set[str] = set()
    seen_domains: set[tuple[str, str]] = set()
    metric_history: dict[
        tuple[str, str, str, str], tuple[AuthorityObservation, AuthorityMetricObservation]
    ] = {}
    for observation in observations:
        links = session.scalars(
            select(BacklinkObservation).where(
                BacklinkObservation.authority_observation_id == observation.id
            )
        ).all()
        domains = session.scalars(
            select(ReferringDomainObservation).where(
                ReferringDomainObservation.authority_observation_id == observation.id
            )
        ).all()
        metrics = session.scalars(
            select(AuthorityMetricObservation).where(
                AuthorityMetricObservation.authority_observation_id == observation.id
            )
        ).all()
        in_window = observation.observed_at >= start
        for link in links:
            first = link.link_identity not in seen_links
            seen_links.add(link.link_identity)
            if not in_window:
                continue
            event_type = None
            if link.link_state is AuthorityLinkState.OBSERVED_LOST:
                event_type = CompetitiveEventType.BACKLINK_LOST
            elif link.link_state is AuthorityLinkState.OBSERVED_NEW:
                event_type = (
                    CompetitiveEventType.BACKLINK_FIRST_OBSERVED
                    if first
                    else CompetitiveEventType.BACKLINK_GAINED
                )
            elif first and link.link_state is AuthorityLinkState.OBSERVED_ACTIVE:
                event_type = CompetitiveEventType.BACKLINK_FIRST_OBSERVED
            if event_type:
                candidates.append(
                    EventCandidate(
                        CompetitiveSubjectType.PAGE,
                        link.link_identity,
                        CompetitiveEventDomain.AUTHORITY,
                        event_type,
                        observation.observed_at,
                        (
                            evidence(
                                observation,
                                "gis_raw.authority_observation",
                                EvidenceRole.PRIMARY,
                                semantic=link.semantic_class,
                            ),
                        ),
                        link.semantic_class,
                        subject_domain=link.source_domain,
                        subject_url=link.target_url,
                        metadata={
                            "source_url": link.source_url,
                            "target_url": link.target_url,
                            "provider": observation.provider,
                            "explicit_link_state": link.link_state.value,
                        },
                    )
                )
        for domain in domains:
            identity = (domain.referring_domain, domain.target_domain)
            first = identity not in seen_domains
            seen_domains.add(identity)
            if not in_window:
                continue
            event_type = None
            if domain.link_state is AuthorityLinkState.OBSERVED_LOST:
                event_type = CompetitiveEventType.REFERRING_DOMAIN_LOST
            elif domain.link_state is AuthorityLinkState.OBSERVED_NEW:
                event_type = (
                    CompetitiveEventType.REFERRING_DOMAIN_FIRST_OBSERVED
                    if first
                    else CompetitiveEventType.REFERRING_DOMAIN_GAINED
                )
            elif first and domain.link_state is AuthorityLinkState.OBSERVED_ACTIVE:
                event_type = CompetitiveEventType.REFERRING_DOMAIN_FIRST_OBSERVED
            if event_type:
                candidates.append(
                    EventCandidate(
                        CompetitiveSubjectType.DOMAIN,
                        f"{domain.referring_domain}|{domain.target_domain}",
                        CompetitiveEventDomain.AUTHORITY,
                        event_type,
                        observation.observed_at,
                        (
                            evidence(
                                observation,
                                "gis_raw.authority_observation",
                                EvidenceRole.PRIMARY,
                                semantic=domain.semantic_class,
                            ),
                        ),
                        domain.semantic_class,
                        subject_domain=domain.referring_domain,
                        magnitude=Decimal(domain.backlink_count),
                        magnitude_unit="backlinks",
                        metadata={
                            "target_domain": domain.target_domain,
                            "provider": observation.provider,
                        },
                    )
                )
        for metric in metrics:
            key = (
                observation.provider,
                observation.target_domain,
                observation.target_url or "",
                f"{metric.metric_provider}:{metric.metric_key}",
            )
            prior = metric_history.get(key)
            metric_history[key] = (observation, metric)
            if not in_window or not prior:
                continue
            before_observation, before_metric = prior
            change = material_numeric_change(
                metric.metric_key,
                before_metric.metric_value,
                metric.metric_value,
                absolute_min=thresholds["authority_metric_absolute_min"],
                percent_min=thresholds["authority_metric_percent_min"],
                increased=CompetitiveEventType.AUTHORITY_METRIC_INCREASED,
                decreased=CompetitiveEventType.AUTHORITY_METRIC_DECREASED,
                unit=metric.unit or metric.metric_key,
            )
            if change:
                candidates.append(
                    EventCandidate(
                        CompetitiveSubjectType.PAGE
                        if observation.target_url
                        else CompetitiveSubjectType.DOMAIN,
                        observation.target_url or observation.target_domain,
                        CompetitiveEventDomain.AUTHORITY,
                        change.event_type,
                        observation.observed_at,
                        pair_evidence(
                            before_observation,
                            observation,
                            "gis_raw.authority_observation",
                            semantic=metric.semantic_class,
                        ),
                        EventSemanticClass.GIS_DERIVED,
                        subject_domain=observation.target_domain,
                        subject_url=observation.target_url,
                        event_subtype=f"{metric.metric_provider}:{metric.metric_key}",
                        magnitude=change.magnitude,
                        magnitude_unit=change.unit,
                        metadata={
                            "metric_provider": metric.metric_provider,
                            "metric_key": metric.metric_key,
                            "before": str(before_metric.metric_value),
                            "after": str(metric.metric_value),
                        },
                    )
                )
    return candidates


ADAPTERS = {
    CompetitiveEventDomain.SERP: synthesize_serp,
    CompetitiveEventDomain.SEARCH_VISIBILITY: synthesize_search,
    CompetitiveEventDomain.CONTENT: synthesize_content,
    CompetitiveEventDomain.TECHNOLOGY: synthesize_technology,
    CompetitiveEventDomain.EXPERIENCE: synthesize_experience,
    CompetitiveEventDomain.AUTHORITY: synthesize_authority,
}


def candidates_for(
    session: Session,
    tenant_id: Any,
    site_id: Any,
    domains: list[CompetitiveEventDomain],
    start: datetime,
    end: datetime,
    raw_thresholds: dict[str, Any],
) -> list[EventCandidate]:
    thresholds = decimal_thresholds(raw_thresholds)
    result: list[EventCandidate] = []
    for domain in domains:
        adapter = ADAPTERS.get(domain)
        if adapter:
            result.extend(adapter(session, tenant_id, site_id, start, end, thresholds))
    return result
