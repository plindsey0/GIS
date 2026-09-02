"""add provider acquisition control plane

Revision ID: 20260902_0029
Revises: 20260902_0028
"""
from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "20260902_0029"
down_revision: Union[str, None] = "20260902_0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE gis_core.provider_definition (
      id uuid PRIMARY KEY, provider_key varchar(100) NOT NULL UNIQUE,
      display_name varchar(255) NOT NULL, description text NOT NULL,
      provider_class varchar(50) NOT NULL, pricing_model varchar(50) NOT NULL,
      implementation_status varchar(50) NOT NULL, is_commercial boolean NOT NULL DEFAULT false,
      documentation_url text, active boolean NOT NULL DEFAULT true,
      metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE gis_core.provider_capability (
      id uuid PRIMARY KEY, provider_id uuid NOT NULL REFERENCES gis_core.provider_definition(id) ON DELETE CASCADE,
      capability_key varchar(100) NOT NULL, display_name varchar(255) NOT NULL, description text NOT NULL,
      unit_type varchar(100) NOT NULL, supports_scheduling boolean NOT NULL DEFAULT false,
      supports_manual_run boolean NOT NULL DEFAULT false, supports_target_scope boolean NOT NULL DEFAULT false,
      default_freshness_seconds integer, metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT uq_provider_capability UNIQUE(provider_id, capability_key)
    );
    CREATE TABLE gis_core.provider_collection_policy (
      id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES gis_core.tenant(id),
      organization_id uuid REFERENCES gis_core.organization(id), site_id uuid,
      provider_id uuid NOT NULL REFERENCES gis_core.provider_definition(id),
      data_source_connection_id uuid REFERENCES gis_core.data_source_connection(id),
      master_enabled boolean NOT NULL DEFAULT false, status varchar(50) NOT NULL DEFAULT 'DISABLED',
      currency varchar(3) NOT NULL DEFAULT 'USD', daily_soft_budget numeric(20,8), daily_hard_budget numeric(20,8),
      monthly_soft_budget numeric(20,8), monthly_hard_budget numeric(20,8), per_run_hard_budget numeric(20,8),
      daily_request_limit integer, monthly_request_limit integer, per_run_request_limit integer,
      allow_unknown_cost boolean NOT NULL DEFAULT false, effective_start_at timestamptz, effective_end_at timestamptz,
      timezone varchar(100) NOT NULL DEFAULT 'UTC', created_by varchar(255) NOT NULL, updated_by varchar(255) NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT uq_provider_policy_scope UNIQUE NULLS NOT DISTINCT(tenant_id, site_id, provider_id),
      CONSTRAINT ck_provider_policy_status CHECK(status IN ('ACTIVE','DISABLED','BLOCKED','PAUSED','MISCONFIGURED','UNAVAILABLE')),
      CONSTRAINT ck_provider_policy_budgets CHECK(
        (daily_soft_budget IS NULL OR daily_soft_budget >= 0) AND (daily_hard_budget IS NULL OR daily_hard_budget >= 0)
        AND (monthly_soft_budget IS NULL OR monthly_soft_budget >= 0) AND (monthly_hard_budget IS NULL OR monthly_hard_budget >= 0)
        AND (per_run_hard_budget IS NULL OR per_run_hard_budget >= 0)),
      CONSTRAINT ck_provider_policy_requests CHECK(
        (daily_request_limit IS NULL OR daily_request_limit >= 0) AND (monthly_request_limit IS NULL OR monthly_request_limit >= 0)
        AND (per_run_request_limit IS NULL OR per_run_request_limit >= 0))
    );
    CREATE INDEX ix_provider_policy_scope ON gis_core.provider_collection_policy(tenant_id, site_id, status);
    CREATE TABLE gis_core.provider_capability_policy (
      id uuid PRIMARY KEY, collection_policy_id uuid NOT NULL REFERENCES gis_core.provider_collection_policy(id) ON DELETE CASCADE,
      capability_id uuid NOT NULL REFERENCES gis_core.provider_capability(id), enabled boolean NOT NULL DEFAULT false,
      cadence varchar(50) NOT NULL DEFAULT 'MANUAL_ONLY', schedule_configuration_json jsonb NOT NULL DEFAULT '{}'::jsonb,
      freshness_target_seconds integer, priority varchar(20) NOT NULL DEFAULT 'STANDARD', per_run_limit integer,
      configuration_json jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(), CONSTRAINT uq_provider_capability_policy UNIQUE(collection_policy_id, capability_id),
      CONSTRAINT ck_provider_capability_cadence CHECK(cadence IN ('MANUAL_ONLY','DAILY','WEEKLY','MONTHLY','CUSTOM_INTERVAL'))
    );
    CREATE TABLE gis_core.provider_collection_target (
      id uuid PRIMARY KEY, capability_policy_id uuid NOT NULL REFERENCES gis_core.provider_capability_policy(id) ON DELETE CASCADE,
      target_type varchar(50) NOT NULL, target_reference_id uuid, target_value text, enabled boolean NOT NULL DEFAULT true,
      priority varchar(20) NOT NULL DEFAULT 'STANDARD', metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_provider_target_identity CHECK(target_reference_id IS NOT NULL OR target_value IS NOT NULL),
      CONSTRAINT uq_provider_collection_target UNIQUE NULLS NOT DISTINCT(capability_policy_id,target_type,target_reference_id,target_value)
    );
    CREATE TABLE gis_core.provider_pricing_configuration (
      id uuid PRIMARY KEY, provider_id uuid NOT NULL REFERENCES gis_core.provider_definition(id),
      capability_id uuid REFERENCES gis_core.provider_capability(id), pricing_model varchar(50) NOT NULL,
      unit_price numeric(20,8), units_per_price numeric(20,8), currency varchar(3) NOT NULL,
      provenance varchar(50) NOT NULL, effective_start_at timestamptz NOT NULL, effective_end_at timestamptz,
      last_verified_at timestamptz, notes text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_provider_pricing_values CHECK((unit_price IS NULL OR unit_price >= 0) AND (units_per_price IS NULL OR units_per_price > 0))
    );
    CREATE INDEX ix_provider_pricing_effective ON gis_core.provider_pricing_configuration(provider_id,effective_start_at);
    CREATE TABLE gis_core.provider_usage_event (
      id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES gis_core.tenant(id), organization_id uuid, site_id uuid,
      provider_id uuid NOT NULL REFERENCES gis_core.provider_definition(id), capability_id uuid REFERENCES gis_core.provider_capability(id),
      collection_policy_id uuid REFERENCES gis_core.provider_collection_policy(id), data_source_connection_id uuid,
      ingestion_run_id uuid, occurred_at timestamptz NOT NULL, request_count integer NOT NULL DEFAULT 0,
      unit_count numeric(20,8) NOT NULL DEFAULT 0, unit_type varchar(100) NOT NULL, estimated_cost numeric(20,8),
      actual_cost numeric(20,8), reserved_cost numeric(20,8) NOT NULL DEFAULT 0, currency varchar(3) NOT NULL,
      cost_semantics varchar(50) NOT NULL, provider_request_id varchar(255), provider_job_id varchar(255),
      status varchar(50) NOT NULL, metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_provider_usage_values CHECK(request_count >= 0 AND unit_count >= 0 AND reserved_cost >= 0 AND (estimated_cost IS NULL OR estimated_cost >= 0) AND (actual_cost IS NULL OR actual_cost >= 0))
    );
    CREATE INDEX ix_provider_usage_scope_time ON gis_core.provider_usage_event(tenant_id,provider_id,occurred_at);
    CREATE TABLE gis_core.provider_policy_audit_event (
      id uuid PRIMARY KEY, tenant_id uuid NOT NULL, site_id uuid, provider_id uuid NOT NULL,
      collection_policy_id uuid, action varchar(100) NOT NULL, actor varchar(255) NOT NULL, reason text,
      before_json jsonb NOT NULL DEFAULT '{}'::jsonb, after_json jsonb NOT NULL DEFAULT '{}'::jsonb,
      occurred_at timestamptz NOT NULL
    );
    CREATE INDEX ix_provider_audit_scope_time ON gis_core.provider_policy_audit_event(tenant_id,provider_id,occurred_at);
    """)
    providers = [
        ("11111111-0000-4000-8000-000000000001","google_search_console","Google Search Console","Customer-connected search performance data.","FREE_FIRST_PARTY","UNKNOWN","IMPLEMENTED",False),
        ("11111111-0000-4000-8000-000000000002","ga4","Google Analytics 4","Customer-connected behavioral analytics.","FREE_FIRST_PARTY","UNKNOWN","IMPLEMENTED",False),
        ("11111111-0000-4000-8000-000000000003","google_pagespeed","Google PageSpeed / CrUX","Lab performance and available field experience data.","FREE_PUBLIC","UNKNOWN","IMPLEMENTED",False),
        ("11111111-0000-4000-8000-000000000004","dataforseo","DataForSEO","Commercial search and domain intelligence.","PAID_USAGE_BASED","PER_REQUEST","IMPLEMENTED",True),
        ("11111111-0000-4000-8000-000000000005","semrush","Semrush","Commercial search intelligence integration.","PAID_SUBSCRIPTION","UNKNOWN","PLANNED",True),
        ("11111111-0000-4000-8000-000000000006","builtwith","BuiltWith","Commercial technology profile intelligence.","PAID_CREDIT_BASED","UNKNOWN","PLANNED",True),
        ("11111111-0000-4000-8000-000000000007","whoisxmlapi","WhoisXMLAPI","Commercial domain registration intelligence.","PAID_CREDIT_BASED","UNKNOWN","PLANNED",True),
    ]
    for row in providers:
        values = ",".join(f"'{value}'" for value in row[:-1])
        commercial = "true" if row[-1] else "false"
        op.execute(
            "INSERT INTO gis_core.provider_definition"
            "(id,provider_key,display_name,description,provider_class,pricing_model,"
            "implementation_status,is_commercial) "
            f"VALUES ({values},{commercial})"
        )
    capabilities = {
      "google_search_console":[("SEARCH_PERFORMANCE","Search performance","Clicks, impressions, click-through rate, and position.","rows",True,True,True)],
      "ga4":[("BEHAVIORAL_ANALYTICS","Behavioral analytics","Sessions, users, landing pages, and events.","rows",True,True,True)],
      "google_pagespeed":[("LAB_PERFORMANCE","Lab performance","Lighthouse laboratory measurements.","urls",True,True,True),("FIELD_CRUX","CrUX field data","Available Chrome field experience measurements.","origins",True,True,True)],
      "dataforseo":[("SERP_COLLECTION","SERP collection","Paid search result collection.","serps",True,True,True),("DOMAIN_SEARCH_INTELLIGENCE","Domain search intelligence","Ranked keywords and competitor-domain evidence.","domains",True,True,True)],
      "semrush":[("DOMAIN_INTELLIGENCE","Domain intelligence","Planned domain intelligence capability.","domains",False,False,True)],
      "builtwith":[("TECHNOLOGY_PROFILE","Technology profile","Planned provider technology profiles.","domains",False,False,True)],
      "whoisxmlapi":[("DOMAIN_REGISTRATION","Domain registration","Planned domain registration metadata.","domains",False,False,True)],
    }
    for provider, rows in capabilities.items():
        for key, name, desc, unit, scheduled, manual, targeted in rows:
            op.execute(f"""INSERT INTO gis_core.provider_capability(id,provider_id,capability_key,display_name,description,unit_type,supports_scheduling,supports_manual_run,supports_target_scope)
            SELECT gen_random_uuid(),id,'{key}','{name}','{desc}','{unit}',{str(scheduled).lower()},{str(manual).lower()},{str(targeted).lower()} FROM gis_core.provider_definition WHERE provider_key='{provider}'""")
    # Preserve existing free collection intent; paid providers remain absent/disabled until explicit configuration.
    op.execute("""INSERT INTO gis_core.provider_collection_policy(id,tenant_id,organization_id,site_id,provider_id,data_source_connection_id,master_enabled,status,created_by,updated_by,timezone)
      SELECT gen_random_uuid(),c.tenant_id,s.organization_id,c.site_id,p.id,c.id,true,'ACTIVE','migration:16a','migration:16a',COALESCE(s.timezone,'UTC')
      FROM gis_core.data_source_connection c JOIN gis_core.data_source d ON d.id=c.data_source_id
      JOIN gis_core.provider_definition p ON p.provider_key=CASE WHEN d.key='pagespeed' THEN 'google_pagespeed' ELSE d.key END LEFT JOIN gis_core.site s ON s.id=c.site_id
      WHERE p.is_commercial=false AND c.status='ACTIVE' ON CONFLICT DO NOTHING""")
    op.execute("""INSERT INTO gis_core.provider_capability_policy(id,collection_policy_id,capability_id,enabled,cadence,priority)
      SELECT gen_random_uuid(),pp.id,pc.id,true,CASE WHEN p.provider_key='google_pagespeed' THEN 'WEEKLY' ELSE 'DAILY' END,'STANDARD'
      FROM gis_core.provider_collection_policy pp JOIN gis_core.provider_definition p ON p.id=pp.provider_id
      JOIN gis_core.provider_capability pc ON pc.provider_id=p.id ON CONFLICT DO NOTHING""")


def downgrade() -> None:
    for name in ["provider_policy_audit_event","provider_usage_event","provider_pricing_configuration","provider_collection_target","provider_capability_policy","provider_collection_policy","provider_capability","provider_definition"]:
        op.execute(f"DROP TABLE gis_core.{name}")
