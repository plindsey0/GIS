from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    AssetLayer,
    AssetType,
    DataAsset,
    DataAssetLineage,
    DataAssetSource,
    DataSource,
    LineageType,
)


class LineageCycleError(ValueError):
    pass


def register_asset(
    session: Session,
    canonical_name: str,
    asset_type: AssetType,
    layer: AssetLayer,
    *,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> DataAsset:
    asset = session.scalar(select(DataAsset).where(DataAsset.canonical_name == canonical_name))
    if asset is None:
        asset = DataAsset(canonical_name=canonical_name, asset_type=asset_type, layer=layer)
        session.add(asset)
        session.flush()
    asset.asset_type = asset_type
    asset.layer = layer
    asset.description = description
    if metadata is not None:
        asset.metadata_json = metadata
    return asset


def _reaches(session: Session, start: uuid.UUID, target: uuid.UUID) -> bool:
    seen: set[uuid.UUID] = set()
    pending = [start]
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(
            session.scalars(
                select(DataAssetLineage.downstream_asset_id).where(
                    DataAssetLineage.upstream_asset_id == current
                )
            ).all()
        )
    return False


def register_lineage(
    session: Session, upstream: DataAsset, downstream: DataAsset, *, reference: str | None = None
) -> DataAssetLineage:
    if upstream.id == downstream.id or _reaches(session, downstream.id, upstream.id):
        raise LineageCycleError("lineage edge would create a cycle")
    edge = session.scalar(
        select(DataAssetLineage).where(
            DataAssetLineage.upstream_asset_id == upstream.id,
            DataAssetLineage.downstream_asset_id == downstream.id,
        )
    )
    if edge is None:
        edge = DataAssetLineage(
            upstream_asset_id=upstream.id,
            downstream_asset_id=downstream.id,
            lineage_type=LineageType.TRANSFORMS,
        )
        session.add(edge)
    edge.transformation_reference = reference
    return edge


def _layer(schema: str) -> AssetLayer:
    return {
        "gis_raw": AssetLayer.RAW,
        "gis_core": AssetLayer.CORE,
        "gis_staging": AssetLayer.STAGING,
        "gis_intermediate": AssetLayer.INTERMEDIATE,
        "gis_analytics": AssetLayer.ANALYTICS,
    }.get(schema, AssetLayer.OTHER)


def register_dbt_manifest(session: Session, path: Path) -> dict[str, int]:
    manifest = json.loads(path.read_text())
    records = {**manifest.get("sources", {}), **manifest.get("nodes", {})}
    assets: dict[str, DataAsset] = {}
    for unique_id, record in records.items():
        if not (unique_id.startswith("source.") or unique_id.startswith("model.")):
            continue
        schema = record["schema"]
        name = record.get("alias") or record.get("identifier") or record["name"]
        assets[unique_id] = register_asset(
            session,
            f"{schema}.{name}",
            AssetType.TABLE if unique_id.startswith("source.") else AssetType.MODEL,
            _layer(schema),
            description=record.get("description") or None,
            metadata={
                "dbt_unique_id": unique_id,
                "original_file_path": record.get("original_file_path"),
            },
        )
    edge_count = 0
    for unique_id, downstream in assets.items():
        for dependency in records[unique_id].get("depends_on", {}).get("nodes", []):
            upstream = assets.get(dependency)
            if upstream:
                register_lineage(session, upstream, downstream, reference=f"dbt:{unique_id}")
                edge_count += 1
    source_map = {
        "gsc_search_observation": "google_search_console",
        "ga4_landing_page_observation": "ga4",
        "ga4_acquisition_observation": "ga4",
        "ga4_event_observation": "ga4",
        "session": "first_party",
        "event": "first_party",
        "calculator_run": "first_party",
        "conversion": "first_party",
        "telemetry_transport_batch": "first_party",
        "serp_observation": "dataforseo",
        "serp_result": "dataforseo",
        "experience_observation": "pagespeed",
        "external_search_observation": "dataforseo",
        "external_keyword_ranking": "dataforseo",
        "external_competitor_observation": "dataforseo",
    }
    link_count = 0
    for asset in assets.values():
        source_key = source_map.get(asset.canonical_name.rsplit(".", 1)[-1])
        source = (
            session.scalar(select(DataSource).where(DataSource.key == source_key))
            if source_key
            else None
        )
        if (
            source
            and session.scalar(
                select(DataAssetSource).where(
                    DataAssetSource.asset_id == asset.id,
                    DataAssetSource.data_source_id == source.id,
                )
            )
            is None
        ):
            session.add(DataAssetSource(asset_id=asset.id, data_source_id=source.id))
            link_count += 1
    session.commit()
    return {"assets": len(assets), "edges": edge_count, "source_links": link_count}


def trace_asset(session: Session, asset: DataAsset) -> dict[str, object]:
    nodes: dict[uuid.UUID, str] = {asset.id: asset.canonical_name}
    edges: list[dict[str, str]] = []
    pending = [asset.id]
    seen: set[uuid.UUID] = set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        for edge in session.scalars(
            select(DataAssetLineage).where(DataAssetLineage.downstream_asset_id == current)
        ).all():
            upstream = session.get(DataAsset, edge.upstream_asset_id)
            if upstream:
                nodes[upstream.id] = upstream.canonical_name
                pending.append(upstream.id)
                edges.append({"upstream": upstream.canonical_name, "downstream": nodes[current]})
    sources = []
    for asset_id, name in nodes.items():
        for link in session.scalars(
            select(DataAssetSource).where(DataAssetSource.asset_id == asset_id)
        ).all():
            source = session.get(DataSource, link.data_source_id)
            sources.append(
                {
                    "asset": name,
                    "source": source.key if source else str(link.data_source_id),
                    "policy_id": str(link.rights_policy_id) if link.rights_policy_id else None,
                }
            )
    return {
        "asset": asset.canonical_name,
        "assets": sorted(nodes.values()),
        "edges": edges,
        "sources": sources,
    }
