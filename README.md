# VAHomeMath Growth Intelligence System

This repository contains the PostgreSQL data platform for the VAHomeMath Growth Intelligence
System (GIS). It provides multi-tenant ownership, source provenance, data-rights metadata,
ingestion-run history, versioned Google Search Console data, aggregate GA4 ingestion, and
canonical first-party product telemetry.

See [local development](docs/gis/local-development.md) for setup commands and
[the architecture](docs/gis/architecture.md) for design context.

After database setup and seeding, configure the first GSC connection:

```bash
gis-gsc configure \
  --tenant vahomemath \
  --site vahomemath \
  --property-uri sc-domain:vahomemath.com \
  --credential-reference env:GSC_SERVICE_ACCOUNT_JSON
gis-gsc validate --connection <connection-uuid>
gis-gsc sync --connection <connection-uuid> --recent-days 3
```

See [the GSC integration guide](docs/gis/gsc-integration.md) before live collection.

GA4 uses the same connection lifecycle with an explicit numeric property ID:

```bash
gis-ga4 configure --tenant vahomemath --site vahomemath \
  --property-id 123456789 \
  --credential-reference env:GA4_SERVICE_ACCOUNT_JSON
gis-ga4 validate --connection <connection-uuid>
gis-ga4 sync --connection <connection-uuid> --recent-days 3 --dataset all
```

See [the GA4 integration guide](docs/gis/ga4-integration.md) for report definitions,
authentication, operational behavior, and interpretation limits.

The first-party telemetry API is documented in
[the telemetry guide](docs/gis/first-party-telemetry.md). It models exact product sessions,
events, calculator runs, and conversions independently from GA4 aggregates.
