from __future__ import annotations

import argparse
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.db import session_factory
from gis.integrations.content_intelligence.retrieval import (
    DirectHTTPRetriever,
    validate_public_http_url,
)
from gis.integrations.content_intelligence.service import discover_content_targets
from gis.integrations.technology_intelligence.service import TechnologyCollector, technology_changes
from gis.models import (
    CompetitiveContentCohort,
    CompetitiveContentCohortMember,
    CompetitiveContentObservation,
    ConnectionStatus,
    ConnectionType,
    DataSource,
    DataSourceConnection,
    PermittedUse,
    Site,
    Technology,
    TechnologyDetection,
    TechnologyObservation,
    Tenant,
)
from gis.provenance.service import evaluate_connection_use


def configure_connection(
    session: Session, tenant_slug: str, site_slug: str
) -> DataSourceConnection:
    tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    site = (
        session.scalar(select(Site).where(Site.tenant_id == tenant.id, Site.slug == site_slug))
        if tenant
        else None
    )
    source = session.scalar(select(DataSource).where(DataSource.key == "direct_technology"))
    if not tenant or not site or not source:
        raise ValueError("tenant, site, or direct-technology source not found")
    connection = session.scalar(
        select(DataSourceConnection).where(
            DataSourceConnection.tenant_id == tenant.id,
            DataSourceConnection.site_id == site.id,
            DataSourceConnection.data_source_id == source.id,
        )
    )
    if connection is None:
        connection = DataSourceConnection(
            tenant_id=tenant.id,
            site_id=site.id,
            data_source_id=source.id,
            connection_type=ConnectionType.NATIVE,
        )
        session.add(connection)
    connection.configuration_json = {
        "adapter": "DIRECT_SIGNATURES",
        "render_mode": "RAW_HTTP",
        "max_targets": 20,
    }
    connection.status = ConnectionStatus.PENDING
    session.commit()
    return connection


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-technology-intelligence")
    commands = root.add_subparsers(dest="command", required=True)
    configure = commands.add_parser("configure")
    configure.add_argument("--tenant", required=True)
    configure.add_argument("--site", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--connection", type=uuid.UUID, required=True)
    collect = commands.add_parser("collect")
    collect.add_argument("--connection", type=uuid.UUID, required=True)
    collect.add_argument("--site", type=uuid.UUID, required=True)
    collect.add_argument("--url", action="append")
    collect.add_argument("--domain", action="append")
    collect.add_argument("--tracked-query-id", type=uuid.UUID)
    collect.add_argument("--cohort-id", type=uuid.UUID)
    collect.add_argument("--top", type=int, default=10)
    collect.add_argument("--scope", choices=("PAGE", "SITE", "DOMAIN"), default="PAGE")
    collect.add_argument("--dry-run", action="store_true")
    estimate = commands.add_parser("estimate")
    estimate.add_argument("--targets", type=int, required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--observation-id", type=uuid.UUID)
    inspect.add_argument("--limit", type=int, default=20)
    technologies = commands.add_parser("technologies")
    technologies.add_argument("--site", type=uuid.UUID, required=True)
    technologies.add_argument("--domain", required=True)
    changes = commands.add_parser("changes")
    changes.add_argument("--site", type=uuid.UUID, required=True)
    changes.add_argument("--domain", required=True)
    compare = commands.add_parser("compare")
    compare.add_argument("--owned-site-id", type=uuid.UUID, required=True)
    compare.add_argument("--cohort-id", type=uuid.UUID, required=True)
    return root


def _cohort_urls(
    session: Session, site_id: uuid.UUID, cohort_id: uuid.UUID, limit: int
) -> list[str]:
    cohort = session.get(CompetitiveContentCohort, cohort_id)
    if not cohort or cohort.site_id != site_id:
        raise ValueError("cohort does not belong to site")
    return list(
        dict.fromkeys(
            session.scalars(
                select(CompetitiveContentObservation.normalized_url)
                .join(
                    CompetitiveContentCohortMember,
                    CompetitiveContentCohortMember.observation_id
                    == CompetitiveContentObservation.id,
                )
                .where(CompetitiveContentCohortMember.cohort_id == cohort.id)
                .limit(limit)
            ).all()
        )
    )


def _latest_detections(
    session: Session, site_id: uuid.UUID, domain: str
) -> list[dict[str, object]]:
    observation = session.scalar(
        select(TechnologyObservation)
        .where(
            TechnologyObservation.site_id == site_id,
            TechnologyObservation.domain == domain.casefold(),
            TechnologyObservation.effective_end.is_(None),
        )
        .order_by(TechnologyObservation.observed_at.desc())
        .limit(1)
    )
    if not observation:
        return []
    rows = session.execute(
        select(TechnologyDetection, Technology)
        .join(Technology, Technology.id == TechnologyDetection.technology_id)
        .where(TechnologyDetection.observation_id == observation.id)
    ).all()
    return [
        {
            "technology": technology.slug,
            "name": technology.name,
            "category": technology.category,
            "version": detection.detected_version,
            "scope": detection.detection_scope,
            "confidence": str(detection.confidence),
            "semantics": detection.semantic_class,
        }
        for detection, technology in rows
    ]


def run(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    try:
        if args.command == "estimate":
            if not 1 <= args.targets <= 20:
                raise ValueError("targets must be between 1 and 20")
            print(
                json.dumps(
                    {
                        "targets": args.targets,
                        "estimated_cost": "0",
                        "currency": "USD",
                        "adapter": "DIRECT_SIGNATURES",
                        "paid_request_performed": False,
                    }
                )
            )
            return 0
        with session_factory()() as session:
            output: object
            if args.command == "configure":
                configured = configure_connection(session, args.tenant, args.site)
                output = {"connection_id": str(configured.id), "status": configured.status.value}
            elif args.command == "validate":
                connection = session.get(DataSourceConnection, args.connection)
                if not connection:
                    raise ValueError("connection not found")
                evaluation = evaluate_connection_use(
                    session, connection, PermittedUse.NORMALIZED_RETENTION
                )
                output = {
                    "connection_id": str(connection.id),
                    "normalized_retention": evaluation.to_dict(),
                    "configuration_valid": True,
                }
                if evaluation.status.value != "ALLOWED":
                    print(json.dumps(output))
                    return 3
            elif args.command == "collect":
                selectors = sum(
                    bool(value)
                    for value in (args.url, args.domain, args.tracked_query_id, args.cohort_id)
                )
                if selectors != 1 or not 1 <= args.top <= 20:
                    raise ValueError("select exactly one target source and a top value from 1-20")
                if args.url:
                    urls = args.url
                elif args.domain:
                    urls = [f"https://{domain.strip().casefold()}/" for domain in args.domain]
                elif args.tracked_query_id:
                    urls = [
                        item.url
                        for item in discover_content_targets(
                            session,
                            args.site,
                            tracked_query_id=args.tracked_query_id,
                            limit=args.top,
                        )
                    ]
                else:
                    urls = _cohort_urls(session, args.site, args.cohort_id, args.top)
                if not 1 <= len(urls) <= 20:
                    raise ValueError("target discovery must produce 1-20 URLs")
                validated_urls = [validate_public_http_url(url) for url in urls]
                if args.dry_run:
                    output = {
                        "targets": validated_urls,
                        "estimated_cost": "0",
                        "currency": "USD",
                        "http_request_performed": False,
                        "paid_request_performed": False,
                    }
                else:
                    runs = [
                        TechnologyCollector(session, DirectHTTPRetriever()).collect(
                            args.connection, args.site, url, observation_scope=args.scope
                        )
                        for url in validated_urls
                    ]
                    output = [
                        {
                            "run_id": str(item.id),
                            "status": item.status.value,
                            "error": item.error_summary,
                        }
                        for item in runs
                    ]
            elif args.command == "inspect":
                statement = (
                    select(TechnologyObservation)
                    .order_by(TechnologyObservation.observed_at.desc())
                    .limit(args.limit)
                )
                if args.observation_id:
                    statement = select(TechnologyObservation).where(
                        TechnologyObservation.id == args.observation_id
                    )
                rows = session.scalars(statement).all()
                output = [
                    {
                        "id": str(row.id),
                        "site_id": str(row.site_id),
                        "domain": row.domain,
                        "url": row.normalized_url,
                        "scope": row.observation_scope,
                        "status": row.collection_status,
                        "observed_at": row.observed_at.isoformat(),
                        "signature_version": row.signature_version,
                    }
                    for row in rows
                ]
            elif args.command == "technologies":
                site = session.get(Site, args.site)
                if not site:
                    raise ValueError("site not found")
                output = _latest_detections(session, site.id, args.domain)
            elif args.command == "changes":
                site = session.get(Site, args.site)
                if not site:
                    raise ValueError("site not found")
                output = technology_changes(session, site.id, args.domain)
            else:
                site = session.get(Site, args.owned_site_id)
                if not site:
                    raise ValueError("owned site not found")
                urls = _cohort_urls(session, site.id, args.cohort_id, 20)
                domains = sorted({url.split("/", 3)[2].removeprefix("www.") for url in urls})
                owned_domain = site.canonical_url.split("/", 3)[2].removeprefix("www.")
                owned: set[str] = {
                    str(item["technology"])
                    for item in _latest_detections(session, site.id, owned_domain)
                }
                prevalence: dict[str, int] = {}
                for domain in domains:
                    for item in _latest_detections(session, site.id, domain):
                        prevalence[str(item["technology"])] = (
                            prevalence.get(str(item["technology"]), 0) + 1
                        )
                output = {
                    "owned_site_id": str(site.id),
                    "cohort_id": str(args.cohort_id),
                    "domain_count": len(domains),
                    "owned_technologies": sorted(owned),
                    "cohort_prevalence": prevalence,
                    "observed_differences": sorted(set(prevalence) - owned),
                    "semantics": "DESCRIPTIVE_NOT_CAUSAL_OR_RECOMMENDATION",
                }
        print(json.dumps(output))
        return 0
    except (ValueError, PermissionError, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error)}))
        return 2


def main() -> None:
    raise SystemExit(run())
