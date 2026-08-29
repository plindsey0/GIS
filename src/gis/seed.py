from __future__ import annotations

import argparse
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.db import session_factory
from gis.models import (
    DataRightsPolicy,
    DataSource,
    Domain,
    DomainType,
    Organization,
    Site,
    SourceType,
    Tenant,
)

TENANT_SLUG = "vahomemath"
SITE_SLUG = "vahomemath"


@dataclass(frozen=True)
class SourceDefinition:
    key: str
    name: str
    provider: str
    source_type: SourceType


SOURCES = (
    SourceDefinition(
        "google_search_console", "Google Search Console", "Google", SourceType.CUSTOMER_CONNECTED
    ),
    SourceDefinition("ga4", "Google Analytics 4", "Google", SourceType.CUSTOMER_CONNECTED),
    SourceDefinition("first_party", "First-party Data", "VAHomeMath", SourceType.FIRST_PARTY),
    SourceDefinition("git", "Git", "Git", SourceType.FIRST_PARTY),
    SourceDefinition("va", "U.S. Department of Veterans Affairs", "VA", SourceType.PUBLIC),
    SourceDefinition("census", "U.S. Census Bureau", "Census", SourceType.PUBLIC),
    SourceDefinition("fhfa", "Federal Housing Finance Agency", "FHFA", SourceType.PUBLIC),
    SourceDefinition("google_ads", "Google Ads", "Google", SourceType.COMMERCIAL),
    SourceDefinition("google_trends", "Google Trends", "Google", SourceType.PUBLIC),
    SourceDefinition("dataforseo", "DataForSEO", "DataForSEO", SourceType.COMMERCIAL),
    SourceDefinition("ahrefs", "Ahrefs", "Ahrefs", SourceType.COMMERCIAL),
    SourceDefinition("semrush", "Semrush", "Semrush", SourceType.COMMERCIAL),
    SourceDefinition("builtwith", "BuiltWith", "BuiltWith", SourceType.COMMERCIAL),
    SourceDefinition("scrapy", "Scrapy", "Scrapy", SourceType.CRAWLED),
    SourceDefinition("playwright", "Playwright", "Microsoft", SourceType.CRAWLED),
    SourceDefinition("manual", "Manual Entry", "GIS", SourceType.MANUAL),
)


def seed(session: Session, hostname: str = "vahomemath.com") -> None:
    """Idempotently bootstrap VAHomeMath and the source registry."""
    unknown_policy = session.scalar(
        select(DataRightsPolicy).where(
            DataRightsPolicy.tenant_id.is_(None),
            DataRightsPolicy.name == "Unreviewed source rights",
        )
    )
    if unknown_policy is None:
        unknown_policy = DataRightsPolicy(
            name="Unreviewed source rights",
            policy_notes="Conservative default until the source license is reviewed.",
        )
        session.add(unknown_policy)
        session.flush()

    for definition in SOURCES:
        source = session.scalar(select(DataSource).where(DataSource.key == definition.key))
        if source is None:
            session.add(
                DataSource(
                    key=definition.key,
                    name=definition.name,
                    provider=definition.provider,
                    source_type=definition.source_type,
                    default_rights_policy_id=unknown_policy.id,
                )
            )

    tenant = session.scalar(select(Tenant).where(Tenant.slug == TENANT_SLUG))
    if tenant is None:
        tenant = Tenant(name="VAHomeMath", slug=TENANT_SLUG)
        session.add(tenant)
        session.flush()

    organization = session.scalar(
        select(Organization).where(
            Organization.tenant_id == tenant.id, Organization.slug == TENANT_SLUG
        )
    )
    if organization is None:
        organization = Organization(tenant_id=tenant.id, name="VAHomeMath", slug=TENANT_SLUG)
        session.add(organization)
        session.flush()

    site = session.scalar(select(Site).where(Site.tenant_id == tenant.id, Site.slug == SITE_SLUG))
    if site is None:
        site = Site(
            tenant_id=tenant.id,
            organization_id=organization.id,
            name="VAHomeMath",
            slug=SITE_SLUG,
            canonical_url=f"https://{hostname}",
            timezone="America/New_York",
        )
        session.add(site)
        session.flush()

    domain = session.scalar(
        select(Domain).where(
            Domain.tenant_id == tenant.id,
            Domain.site_id == site.id,
            Domain.hostname == hostname,
        )
    )
    if domain is None:
        session.add(
            Domain(
                tenant_id=tenant.id,
                site_id=site.id,
                hostname=hostname,
                domain_type=DomainType.PRIMARY,
                is_primary=True,
            )
        )
    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the GIS development database")
    parser.add_argument(
        "--hostname",
        default="vahomemath.com",
        help="VAHomeMath production hostname (default: vahomemath.com)",
    )
    args = parser.parse_args()
    with session_factory()() as session:
        seed(session, hostname=args.hostname.lower().strip())


if __name__ == "__main__":
    main()
