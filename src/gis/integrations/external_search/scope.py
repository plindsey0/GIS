from __future__ import annotations

from sqlalchemy import and_, or_
from sqlalchemy.sql.elements import ColumnElement

from gis.integrations.serp.dataforseo import COUNTRY_LOCATION_CODES
from gis.models import ExternalSearchObservation


def country_scope(country_code: str) -> ColumnElement[bool]:
    """Match canonical country metadata, including legacy rows with only a location code."""
    location_code = COUNTRY_LOCATION_CODES.get(country_code.upper())
    fallback = and_(
        or_(
            ExternalSearchObservation.country_code.is_(None),
            ExternalSearchObservation.country_code == "",
        ),
        ExternalSearchObservation.location_code == location_code,
    )
    return or_(ExternalSearchObservation.country_code == country_code.upper(), fallback)
