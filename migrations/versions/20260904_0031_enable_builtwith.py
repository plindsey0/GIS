"""Register the governed BuiltWith adapter; authorize no collection."""

from alembic import op

revision = "20260904_0031"
down_revision = "20260903_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""UPDATE gis_core.provider_definition SET implementation_status='IMPLEMENTED'
                  WHERE provider_key='builtwith'""")
    op.execute("""UPDATE gis_core.provider_capability SET display_name='Technology profile intelligence',
                  description='Named technologies and categories from one BuiltWith Domain API lookup.'
                  WHERE capability_key='TECHNOLOGY_PROFILE' AND provider_id IN
                  (SELECT id FROM gis_core.provider_definition WHERE provider_key='builtwith')""")
    op.execute("""UPDATE gis_core.data_source SET acquisition_method='LICENSED_API'
                  WHERE key='builtwith'""")


def downgrade() -> None:
    op.execute("""UPDATE gis_core.provider_definition SET implementation_status='PLANNED'
                  WHERE provider_key='builtwith'""")
    op.execute("""UPDATE gis_core.provider_capability SET display_name='Technology profile',
                  description='Planned provider technology profiles.'
                  WHERE capability_key='TECHNOLOGY_PROFILE' AND provider_id IN
                  (SELECT id FROM gis_core.provider_definition WHERE provider_key='builtwith')""")
    op.execute("UPDATE gis_core.data_source SET acquisition_method='UNKNOWN' WHERE key='builtwith'")
