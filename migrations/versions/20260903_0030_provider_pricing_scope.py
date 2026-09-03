"""Scope operator pricing assumptions to a tenant/site.

Revision ID: 20260903_0030
Revises: 20260902_0029
"""

import sqlalchemy as sa
from alembic import op

revision = "20260903_0030"
down_revision = "20260902_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_pricing_configuration",
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("gis_core.tenant.id")),
        schema="gis_core",
    )
    op.add_column(
        "provider_pricing_configuration",
        sa.Column("site_id", sa.UUID(), sa.ForeignKey("gis_core.site.id")),
        schema="gis_core",
    )
    op.create_foreign_key(
        "fk_provider_pricing_scope",
        "provider_pricing_configuration",
        "site",
        ["tenant_id", "site_id"],
        ["tenant_id", "id"],
        source_schema="gis_core",
        referent_schema="gis_core",
    )
    op.create_check_constraint(
        "ck_provider_pricing_scope_pair",
        "provider_pricing_configuration",
        "(tenant_id IS NULL) = (site_id IS NULL)",
        schema="gis_core",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_provider_pricing_scope_pair", "provider_pricing_configuration", schema="gis_core"
    )
    op.drop_constraint(
        "fk_provider_pricing_scope", "provider_pricing_configuration", schema="gis_core"
    )
    op.drop_column("provider_pricing_configuration", "site_id", schema="gis_core")
    op.drop_column("provider_pricing_configuration", "tenant_id", schema="gis_core")
