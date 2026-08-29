# GIS data-platform architecture

## Purpose

GIS is the decision-intelligence layer above VAHomeMath's operational systems. Epic 1 only
creates the durable PostgreSQL foundation. Future epics will add typed observations and
decision objects; this epic does not ingest provider data or expose user-facing behavior.

VAHomeMath is the first tenant and site, but no table assumes it is the only one. UUIDs are
internal identifiers; slugs and provider identifiers are stable lookup attributes rather than
primary keys.

## Namespaces

Core relational objects live in the PostgreSQL `gis_core` schema. `gis_raw` and
`gis_analytics` are reserved architectural names, but are intentionally not created until a
future epic has concrete objects for them. This keeps the initial migration small and avoids
empty namespace sprawl.

## Ownership and integrity

Tenant identity is explicit on every tenant-scoped table. Composite foreign keys ensure a
site, domain, connection, or ingestion run cannot accidentally point across tenants. A site
belongs to an organization in the same tenant. A connection may be tenant-wide or site-bound.

The source registry is global because provider definitions such as Google Search Console are
shared vocabulary, not customer data. Its connections are tenant-owned. Rights policies may
be global defaults (`tenant_id` is null) or tenant-specific overrides. A connection's optional
`rights_policy_id` is the designed override point for its source default. Composite integrity
requires an override policy to belong to the same tenant; global policies remain source defaults.

## Provenance and history

Observations are append-oriented. Do not update historical facts to represent a newer sample.
The `ProvenanceMixin` defines the conventional columns for future typed observation models:

- source connection and source record identifier;
- ingestion batch/run;
- observed, ingested, and effective timestamps;
- confidence and quality flag;
- external raw-payload reference;
- the rights policy governing the observation.

Future tables should copy or use this clear column convention and add their own domain-specific
columns. They should not create a universal observation table, ORM inheritance hierarchy, or
entity-attribute-value model. Add indexes based on actual query shapes, commonly tenant/site,
observation time, source connection, and batch.

Raw payload references point to managed external storage; payloads and credentials do not
belong in ordinary relational credential fields. `credential_reference` stores a secret-manager
reference only.

## Time and configuration

All event timestamps use PostgreSQL `timestamp with time zone` and applications should write
UTC. `site.timezone` separately retains the IANA business timezone. Provider-specific,
non-secret connection settings may use `configuration_json`; stable ownership and policy
concepts remain relational.
