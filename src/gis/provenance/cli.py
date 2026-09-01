from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from sqlalchemy import select

from gis.db import session_factory
from gis.models import (
    DataAsset,
    DataAssetLineage,
    DataRightsGrant,
    DataRightsPolicy,
    DataSource,
    PermittedUse,
    RightsStatus,
)
from gis.provenance.activation import activate_reviewed_policies, activate_safe_schedules
from gis.provenance.lineage import register_dbt_manifest, trace_asset
from gis.provenance.service import evaluate_asset_use, evaluate_source_use


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="gis-provenance", description="Inspect GIS rights and provenance"
    )
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("source", "policy", "lineage", "trace"):
        command = commands.add_parser(name)
        command.add_argument("identifier")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("identifier")
    evaluate.add_argument("--use", required=True, choices=[item.value for item in PermittedUse])
    evaluate.add_argument(
        "--asset", action="store_true", help="interpret identifier as a data asset"
    )
    register = commands.add_parser("register-dbt")
    register.add_argument("--manifest", type=Path, default=Path("analytics/target/manifest.json"))
    activate = commands.add_parser("activate-reviewed")
    activate.add_argument("--tenant", type=uuid.UUID, required=True)
    schedules = commands.add_parser("activate-safe-schedules")
    schedules.add_argument("--tenant", type=uuid.UUID, required=True)
    schedules.add_argument("--site", type=uuid.UUID, required=True)
    schedules.add_argument("--market", type=uuid.UUID, required=True)
    schedules.add_argument("--gsc-connection", type=uuid.UUID, required=True)
    schedules.add_argument("--ga4-connection", type=uuid.UUID, required=True)
    schedules.add_argument("--google-validated", action="store_true")
    return root


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def run(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    with session_factory()() as session:
        if args.command == "activate-reviewed":
            activated = activate_reviewed_policies(session, args.tenant)
            _print({"activated": {key: str(value) for key, value in activated.items()}})
            return 0
        if args.command == "activate-safe-schedules":
            configured = activate_safe_schedules(
                session,
                args.tenant,
                args.site,
                args.market,
                args.gsc_connection,
                args.ga4_connection,
                google_validated=args.google_validated,
            )
            _print({"configured": configured})
            return 0
        if args.command == "register-dbt":
            if not args.manifest.is_file():
                _print({"error": "manifest not found", "path": str(args.manifest)})
                return 2
            _print(register_dbt_manifest(session, args.manifest))
            return 0
        if args.command in {"lineage", "trace"} or (args.command == "evaluate" and args.asset):
            asset = session.scalar(
                select(DataAsset).where(DataAsset.canonical_name == args.identifier)
            )
            if asset is None:
                _print({"error": "asset not found", "asset": args.identifier})
                return 2
            if args.command == "trace":
                _print(trace_asset(session, asset))
                return 0
            if args.command == "lineage":
                upstream = session.scalars(
                    select(DataAssetLineage).where(DataAssetLineage.downstream_asset_id == asset.id)
                ).all()
                _print(
                    {
                        "asset": asset.canonical_name,
                        "upstream_asset_ids": [str(edge.upstream_asset_id) for edge in upstream],
                    }
                )
                return 0
            evaluation = evaluate_asset_use(session, asset, PermittedUse(args.use))
            _print(evaluation.to_dict())
            return {RightsStatus.ALLOWED: 0, RightsStatus.DENIED: 3, RightsStatus.UNKNOWN: 4}[
                evaluation.status
            ]
        source = session.scalar(select(DataSource).where(DataSource.key == args.identifier))
        if source is None:
            _print({"error": "source not found", "source": args.identifier})
            return 2
        policy = (
            session.get(DataRightsPolicy, source.default_rights_policy_id)
            if source.default_rights_policy_id
            else None
        )
        if args.command == "source":
            _print(
                {
                    "key": source.key,
                    "name": source.name,
                    "provider": source.provider,
                    "source_type": source.source_type.value,
                    "acquisition_method": source.acquisition_method.value,
                    "active": source.is_active,
                    "authoritative_url": source.authoritative_url,
                    "terms_url": source.terms_url,
                    "default_policy_id": str(source.default_rights_policy_id)
                    if source.default_rights_policy_id
                    else None,
                }
            )
            return 0
        if args.command == "policy":
            if policy is None:
                _print({"source": source.key, "policy": None})
                return 4
            grants = session.scalars(
                select(DataRightsGrant).where(DataRightsGrant.policy_id == policy.id)
            ).all()
            _print(
                {
                    "source": source.key,
                    "policy": {
                        "id": str(policy.id),
                        "name": policy.name,
                        "version": policy.policy_version,
                        "documented_basis": policy.documented_basis,
                        "reviewed_at": policy.reviewed_at,
                        "review_authority": policy.review_authority,
                        "grants": {
                            grant.permitted_use.value: grant.status.value for grant in grants
                        },
                    },
                }
            )
            return 0
        evaluation = evaluate_source_use(session, source, PermittedUse(args.use))
        _print(evaluation.to_dict())
        return {RightsStatus.ALLOWED: 0, RightsStatus.DENIED: 3, RightsStatus.UNKNOWN: 4}[
            evaluation.status
        ]


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
