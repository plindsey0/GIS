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
from gis.integrations.content_intelligence.service import (
    CompetitiveContentCollector,
    create_cohort,
    discover_content_targets,
)
from gis.models import (
    CompetitiveContentCohortMember,
    CompetitiveContentDocument,
    CompetitiveContentObservation,
    ConnectionStatus,
    ConnectionType,
    DataSource,
    DataSourceConnection,
    PermittedUse,
    Site,
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
    source = session.scalar(select(DataSource).where(DataSource.key == "direct_http"))
    if not tenant or not site or not source:
        raise ValueError("tenant, site, or public-web source not found")
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
        "adapter": "DIRECT_HTTP",
        "render_mode": "RAW_HTTP",
        "max_pages_per_command": 20,
    }
    connection.status = ConnectionStatus.PENDING
    session.commit()
    return connection


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-content-intelligence")
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
    collect.add_argument("--tracked-query-id", type=uuid.UUID)
    collect.add_argument("--external-search-observation-id", type=uuid.UUID)
    collect.add_argument("--domain")
    collect.add_argument("--top", type=int, default=10)
    collect.add_argument("--dry-run", action="store_true")
    estimate = commands.add_parser("estimate")
    estimate.add_argument("--pages", type=int, required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--observation-id", type=uuid.UUID)
    inspect.add_argument("--limit", type=int, default=20)
    cohort = commands.add_parser("cohort")
    cohort.add_argument("--site", type=uuid.UUID, required=True)
    cohort.add_argument("--name", required=True)
    cohort.add_argument("--observation-id", type=uuid.UUID, action="append", required=True)
    cohort.add_argument("--tracked-query-id", type=uuid.UUID)
    compare = commands.add_parser("compare")
    compare.add_argument("--cohort", type=uuid.UUID, required=True)
    compare.add_argument("--owned-observation", type=uuid.UUID, required=True)
    return root


def _inspection(
    row: CompetitiveContentObservation, document: CompetitiveContentDocument | None
) -> dict[str, object]:
    return {
        "id": str(row.id),
        "site_id": str(row.site_id),
        "url": row.normalized_url,
        "domain": row.domain,
        "ownership": row.ownership_class,
        "observed_at": row.observed_at.isoformat(),
        "status": row.retrieval_status,
        "render_mode": row.render_mode,
        "content_hash": row.content_hash,
        "raw_retained": row.raw_retained,
        "word_count": document.normalized_word_count if document else None,
    }


def run(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    try:
        if args.command == "estimate":
            if not 1 <= args.pages <= 20:
                raise ValueError("pages must be between 1 and 20")
            print(
                json.dumps(
                    {
                        "pages": args.pages,
                        "estimated_cost": "0",
                        "currency": "USD",
                        "adapter": "DIRECT_HTTP",
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
                validated = session.get(DataSourceConnection, args.connection)
                if not validated:
                    raise ValueError("connection not found")
                evaluation = evaluate_connection_use(
                    session, validated, PermittedUse.NORMALIZED_RETENTION
                )
                output = {
                    "connection_id": str(validated.id),
                    "normalized_retention": evaluation.to_dict(),
                    "configuration_valid": True,
                }
                if evaluation.status.value != "ALLOWED":
                    print(json.dumps(output))
                    return 3
            elif args.command == "collect":
                if args.url and args.external_search_observation_id:
                    raise ValueError("explicit URLs cannot be combined with external discovery")
                if args.url:
                    if not 1 <= len(args.url) <= 20:
                        raise ValueError("collect accepts 1-20 URLs")
                    targets = [
                        {
                            "url": validate_public_http_url(value),
                            "tracked_query_id": args.tracked_query_id,
                            "serp_result_id": None,
                            "external_search_observation_id": None,
                        }
                        for value in args.url
                    ]
                else:
                    discovered = discover_content_targets(
                        session,
                        args.site,
                        tracked_query_id=args.tracked_query_id,
                        external_search_observation_id=args.external_search_observation_id,
                        domain=args.domain,
                        limit=args.top,
                    )
                    targets = [
                        {
                            "url": item.url,
                            "tracked_query_id": item.tracked_query_id,
                            "serp_result_id": item.serp_result_id,
                            "external_search_observation_id": item.external_search_observation_id,
                        }
                        for item in discovered
                    ]
                if not targets:
                    raise ValueError("discovery returned no collection targets")
                if args.dry_run:
                    output = {
                        "targets": targets,
                        "estimated_cost": "0",
                        "currency": "USD",
                        "paid_request_performed": False,
                        "http_request_performed": False,
                    }
                else:
                    runs = [
                        CompetitiveContentCollector(session, DirectHTTPRetriever()).collect(
                            args.connection,
                            args.site,
                            str(target["url"]),
                            tracked_query_id=target["tracked_query_id"],
                            serp_result_id=target["serp_result_id"],
                            external_search_observation_id=target["external_search_observation_id"],
                        )
                        for target in targets
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
                    select(CompetitiveContentObservation)
                    .order_by(CompetitiveContentObservation.observed_at.desc())
                    .limit(args.limit)
                )
                if args.observation_id:
                    statement = select(CompetitiveContentObservation).where(
                        CompetitiveContentObservation.id == args.observation_id
                    )
                rows = session.scalars(statement).all()
                output = [
                    _inspection(row, session.get(CompetitiveContentDocument, row.id))
                    for row in rows
                ]
            elif args.command == "cohort":
                cohort = create_cohort(
                    session,
                    args.site,
                    args.name,
                    args.observation_id,
                    tracked_query_id=args.tracked_query_id,
                )
                output = {
                    "cohort_id": str(cohort.id),
                    "member_count": len(args.observation_id),
                    "frozen_at": cohort.frozen_at.isoformat(),
                }
            else:
                owned = session.get(CompetitiveContentObservation, args.owned_observation)
                if not owned:
                    raise ValueError("owned observation not found")
                members = session.scalars(
                    select(CompetitiveContentCohortMember).where(
                        CompetitiveContentCohortMember.cohort_id == args.cohort
                    )
                ).all()
                competitor_documents: list[CompetitiveContentDocument] = []
                for member in members:
                    document = session.get(CompetitiveContentDocument, member.observation_id)
                    if member.observation_id != owned.id and document is not None:
                        competitor_documents.append(document)
                owned_document = session.get(CompetitiveContentDocument, owned.id)
                if not owned_document or not competitor_documents:
                    raise ValueError("comparison requires owned and competitor documents")
                ordered_words = sorted(item.normalized_word_count for item in competitor_documents)
                output = {
                    "cohort_id": str(args.cohort),
                    "owned_observation_id": str(owned.id),
                    "competitor_count": len(competitor_documents),
                    "owned_word_count": owned_document.normalized_word_count,
                    "competitor_median_word_count": ordered_words[len(ordered_words) // 2],
                    "semantics": "OBSERVED_DESCRIPTIVE_NOT_CAUSAL",
                }
        print(json.dumps(output))
        return 0
    except (ValueError, PermissionError, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error)}))
        return 2


def main() -> None:
    raise SystemExit(run())
