# PageSpeed and CrUX operations

GIS stores PageSpeed Insights results as two distinct evidence classes: Lighthouse `LAB` observations and CrUX `FIELD` observations. LAB data is never substituted for absent FIELD data. A successful response with no CrUX population therefore remains an honest `NO_FIELD_DATA_AVAILABLE` state, not a zero and not a collector failure.

The governed connection stores only `env:GIS_PAGESPEED_API_KEY`. The credential value belongs in `~/.config/gis/secrets/pagespeed.env` as `GIS_PAGESPEED_API_KEY=...`, with owner-only permissions (`chmod 600`). The orchestration worker reads only the referenced variable, only when starting the allowlisted experience collector. It fails closed if the reference, file, permissions, or variable is invalid. The value is not copied into schedules, launch configuration, database rows, or logs.

The enabled schedule is limited to the configured VAHomeMath URL, mobile form factor, URL scope, and an asserted actual provider cost of zero. Enabling requires an active tenant/site-scoped connection, the exact environment reference, reviewed rights, and explicit validation backed by a prior successful ingestion. Paid collectors remain disabled.

Operational validation does not require another live API request: `gis-experience validate --connection <uuid>` can validate configuration and persist connection health from an existing successful ingestion run. HTTP failures are recorded only as a bounded status such as `PageSpeed HTTP 429`; arbitrary provider or exception text is reduced to its exception class.
