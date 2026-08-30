from __future__ import annotations

import json
from contextlib import nullcontext
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    AcquisitionMethod,
    AssetLayer,
    AssetType,
    ConnectionStatus,
    ConnectionType,
    DataAsset,
    DataAssetSource,
    DataRightsGrant,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    IngestionRun,
    IngestionStatus,
    PermittedUse,
    RightsStatus,
    Site,
    SourceType,
    Tenant,
)
from gis.provenance.cli import run
from gis.provenance.lineage import (
    LineageCycleError,
    register_asset,
    register_dbt_manifest,
    register_lineage,
    trace_asset,
)
from gis.provenance.service import (
    RightsNotAllowedError,
    assert_use_allowed,
    evaluate_asset_use,
    evaluate_connection_use,
    evaluate_policy_use,
)
from gis.seed import seed


def policy(session: Session, name: str, status: RightsStatus) -> DataRightsPolicy:
    item = DataRightsPolicy(name=name, policy_version="1")
    session.add(item)
    session.flush()
    session.add(
        DataRightsGrant(
            policy_id=item.id,
            permitted_use=PermittedUse.EXTERNAL_PUBLICATION,
            status=status,
            reason=f"{name} decision",
        )
    )
    session.flush()
    return item


def source(session: Session, key: str, rights: DataRightsPolicy) -> DataSource:
    item = DataSource(
        key=key,
        name=key,
        provider="Test",
        source_type=SourceType.MANUAL,
        acquisition_method=AcquisitionMethod.MANUAL_IMPORT,
        default_rights_policy_id=rights.id,
    )
    session.add(item)
    session.flush()
    return item


def test_policy_versioning_and_allowed_denied_unknown(session: Session) -> None:
    allowed = policy(session, "allowed", RightsStatus.ALLOWED)
    denied = policy(session, "denied", RightsStatus.DENIED)
    unknown = DataRightsPolicy(name="unknown", policy_version="2", supersedes_policy_id=allowed.id)
    session.add(unknown)
    session.flush()
    assert (
        evaluate_policy_use(session, allowed, PermittedUse.EXTERNAL_PUBLICATION).status
        is RightsStatus.ALLOWED
    )
    assert (
        evaluate_policy_use(session, denied, PermittedUse.EXTERNAL_PUBLICATION).status
        is RightsStatus.DENIED
    )
    assert (
        evaluate_policy_use(session, unknown, PermittedUse.EXTERNAL_PUBLICATION).status
        is RightsStatus.UNKNOWN
    )
    assert unknown.supersedes_policy_id == allowed.id


def test_fail_closed_enforcement(session: Session) -> None:
    evaluation = evaluate_policy_use(
        session, DataRightsPolicy(name="unreviewed"), PermittedUse.RAG_RETRIEVAL
    )
    with pytest.raises(RightsNotAllowedError):
        assert_use_allowed(evaluation)


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([RightsStatus.ALLOWED, RightsStatus.ALLOWED], RightsStatus.ALLOWED),
        ([RightsStatus.ALLOWED, RightsStatus.UNKNOWN], RightsStatus.UNKNOWN),
        ([RightsStatus.ALLOWED, RightsStatus.UNKNOWN, RightsStatus.DENIED], RightsStatus.DENIED),
    ],
)
def test_asset_evaluation_is_conservative(
    session: Session, statuses: list[RightsStatus], expected: RightsStatus
) -> None:
    asset = register_asset(
        session,
        f"gis_analytics.asset_{expected.value}_{len(statuses)}",
        AssetType.MODEL,
        AssetLayer.ANALYTICS,
    )
    for index, status in enumerate(statuses):
        rights = policy(session, f"policy-{expected.value}-{index}", status)
        provider = source(session, f"source-{expected.value}-{index}", rights)
        session.add(DataAssetSource(asset_id=asset.id, data_source_id=provider.id))
    session.flush()
    assert evaluate_asset_use(session, asset, PermittedUse.EXTERNAL_PUBLICATION).status is expected


def test_connection_override_resolves_before_source_policy(session: Session) -> None:
    seed(session, hostname="provenance.test")
    provider = session.scalar(select(DataSource).where(DataSource.key == "first_party"))
    assert provider
    owner = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    web = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert owner and web
    override = policy(session, "connection override", RightsStatus.ALLOWED)
    override.tenant_id = owner.id
    connection = DataSourceConnection(
        tenant_id=owner.id,
        site_id=web.id,
        data_source_id=provider.id,
        rights_policy_id=override.id,
        connection_type=ConnectionType.CUSTOMER_SIDE,
        status=ConnectionStatus.ACTIVE,
    )
    session.add(connection)
    session.flush()
    assert (
        evaluate_connection_use(session, connection, PermittedUse.EXTERNAL_PUBLICATION).status
        is RightsStatus.ALLOWED
    )


def test_ingestion_run_captures_policy_and_acquisition(session: Session) -> None:
    seed(session, hostname="run-provenance.test")
    owner = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    web = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    provider = session.scalar(select(DataSource).where(DataSource.key == "ga4"))
    assert owner and web and provider and provider.default_rights_policy_id
    connection = DataSourceConnection(
        tenant_id=owner.id,
        site_id=web.id,
        data_source_id=provider.id,
        connection_type=ConnectionType.NATIVE,
        status=ConnectionStatus.ACTIVE,
    )
    session.add(connection)
    session.flush()
    run_item = IngestionRun(
        tenant_id=owner.id,
        site_id=web.id,
        data_source_connection_id=connection.id,
        started_at=datetime.now(timezone.utc),
        status=IngestionStatus.RUNNING,
        rights_policy_id=provider.default_rights_policy_id,
        acquisition_method=provider.acquisition_method,
        collector_name="test",
        collector_version="1",
    )
    session.add(run_item)
    session.flush()
    assert run_item.rights_policy_id == provider.default_rights_policy_id
    assert run_item.acquisition_method is AcquisitionMethod.AUTHENTICATED_API


def test_lineage_traversal_and_cycle_prevention(session: Session) -> None:
    raw = register_asset(session, "gis_raw.example", AssetType.TABLE, AssetLayer.RAW)
    staging = register_asset(session, "gis_staging.example", AssetType.MODEL, AssetLayer.STAGING)
    mart = register_asset(session, "gis_analytics.example", AssetType.MODEL, AssetLayer.ANALYTICS)
    register_lineage(session, raw, staging)
    register_lineage(session, staging, mart)
    session.flush()
    traced = trace_asset(session, mart)
    assert traced["assets"] == ["gis_analytics.example", "gis_raw.example", "gis_staging.example"]
    with pytest.raises(LineageCycleError):
        register_lineage(session, mart, raw)


def test_dbt_manifest_registration(session: Session, tmp_path) -> None:  # type: ignore[no-untyped-def]
    seed(session, hostname="manifest.test")
    manifest = {
        "sources": {
            "source.test.raw.gsc_search_observation": {
                "schema": "gis_raw",
                "identifier": "gsc_search_observation",
                "name": "gsc_search_observation",
                "depends_on": {"nodes": []},
            }
        },
        "nodes": {
            "model.test.stg": {
                "schema": "gis_staging",
                "alias": "stg_search",
                "name": "stg",
                "original_file_path": "models/stg.sql",
                "depends_on": {"nodes": ["source.test.raw.gsc_search_observation"]},
            },
            "model.test.mart": {
                "schema": "gis_analytics",
                "alias": "mart_search",
                "name": "mart",
                "original_file_path": "models/mart.sql",
                "depends_on": {"nodes": ["model.test.stg"]},
            },
        },
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    result = register_dbt_manifest(session, path)
    assert result == {"assets": 3, "edges": 2, "source_links": 1}
    mart = session.scalar(
        select(DataAsset).where(DataAsset.canonical_name == "gis_analytics.mart_search")
    )
    assert mart
    assert "gis_raw.gsc_search_observation" in trace_asset(session, mart)["assets"]


def test_cli_inspection_evaluation_and_trace_do_not_expose_credentials(
    session: Session, monkeypatch, capsys
) -> None:  # type: ignore[no-untyped-def]
    rights = policy(session, "cli allowed", RightsStatus.ALLOWED)
    provider = source(session, "cli-source", rights)
    asset = register_asset(
        session, "gis_analytics.cli_asset", AssetType.MODEL, AssetLayer.ANALYTICS
    )
    session.add(DataAssetSource(asset_id=asset.id, data_source_id=provider.id))
    session.flush()
    monkeypatch.setattr("gis.provenance.cli.session_factory", lambda: lambda: nullcontext(session))
    assert run(["source", "cli-source"]) == 0
    assert run(["policy", "cli-source"]) == 0
    assert run(["evaluate", "cli-source", "--use", "external_publication"]) == 0
    assert run(["trace", "gis_analytics.cli_asset"]) == 0
    output = capsys.readouterr().out.lower()
    assert (
        "credential_reference" not in output and "secret" not in output and "password" not in output
    )
