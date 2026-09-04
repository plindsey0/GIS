"""Required-ingestion contract, shared by execution and read-only interpretation."""

from __future__ import annotations

from gis.models import FailureCategory, IngestionRun, IngestionStatus
from gis.orchestration.reliability import ClassifiedFailure


def ingestion_failure(ingestion: IngestionRun) -> ClassifiedFailure | None:
    if ingestion.status == IngestionStatus.SUCCEEDED and not ingestion.error_count:
        return None
    detail = ingestion.error_summary or f"Required ingestion ended in {ingestion.status.value}"
    category = FailureCategory.INTERNAL_PROCESSING_ERROR
    recorded = (ingestion.source_metadata or {}).get("failure_category")
    if recorded:
        try:
            category = FailureCategory(recorded)
        except ValueError:
            pass
    elif "DataForSEO Labs requires a location target" in detail:
        category = FailureCategory.CONFIGURATION_ERROR
        detail = "DataForSEO Domain Search request was missing required GIS location context; rejected locally before HTTP dispatch."
    return ClassifiedFailure(category, detail)
