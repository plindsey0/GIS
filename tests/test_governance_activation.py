from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    DataRightsGrant,
    DataRightsPolicy,
    DataSource,
    PermittedUse,
    RightsStatus,
    Tenant,
)
from gis.provenance.activation import POLICY_VERSION, activate_reviewed_policies
from gis.seed import seed


def test_activation_is_explicit_source_scoped_and_idempotent(session: Session) -> None:
    seed(session, hostname="governance.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    assert tenant
    first = activate_reviewed_policies(session, tenant.id)
    second = activate_reviewed_policies(session, tenant.id)
    assert first == second
    assert set(first) == {
        "google_search_console",
        "ga4",
        "first_party",
        "dataforseo",
        "direct_http",
        "direct_technology",
    }
    for source_key, policy_id in first.items():
        source = session.scalar(select(DataSource).where(DataSource.key == source_key))
        policy = session.get(DataRightsPolicy, policy_id)
        assert source and source.default_rights_policy_id == policy_id
        assert policy and policy.policy_version == POLICY_VERSION
        grants = {
            row.permitted_use: row.status
            for row in session.scalars(
                select(DataRightsGrant).where(DataRightsGrant.policy_id == policy_id)
            )
        }
        assert grants[PermittedUse.AGGREGATE_STATISTICS] is RightsStatus.ALLOWED
        assert grants[PermittedUse.DERIVATIVE_CREATION] is RightsStatus.ALLOWED
        assert grants[PermittedUse.CUSTOMER_FACING_DISPLAY] is RightsStatus.ALLOWED
        assert grants[PermittedUse.EXTERNAL_PUBLICATION] is RightsStatus.DENIED
        assert grants[PermittedUse.AI_INFERENCE] is RightsStatus.UNKNOWN
