# VAHomeMath Growth Intelligence System

This repository contains the PostgreSQL data platform for the VAHomeMath Growth Intelligence
System (GIS). It provides multi-tenant ownership, source provenance, data-rights metadata,
ingestion-run history, and versioned Google Search Console Search Analytics ingestion.

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
