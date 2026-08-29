from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any


class GSCConfigurationError(ValueError):
    pass


class CollectionGrain(str, enum.Enum):
    QUERY_PAGE = "query-page"
    PAGE = "page"

    @property
    def required_dimensions(self) -> tuple[str, ...]:
        if self is CollectionGrain.QUERY_PAGE:
            return ("date", "query", "page")
        return ("date", "page")


SUPPORTED_OPTIONAL_DIMENSIONS = ("country", "device", "searchAppearance")
SUPPORTED_SEARCH_TYPES = ("web",)
SUPPORTED_AUTH_MODES = ("service_account", "oauth")


@dataclass(frozen=True)
class GSCConnectionConfig:
    property_uri: str
    collection_grain: CollectionGrain = CollectionGrain.QUERY_PAGE
    search_type: str = "web"
    optional_dimensions: tuple[str, ...] = ()
    country: str | None = None
    device: str | None = None
    auth_mode: str = "service_account"

    @property
    def dimensions(self) -> tuple[str, ...]:
        return self.collection_grain.required_dimensions + self.optional_dimensions

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> GSCConnectionConfig:
        property_uri = value.get("property_uri")
        if not isinstance(property_uri, str) or not property_uri.strip():
            raise GSCConfigurationError("configuration_json.property_uri is required")
        if not (
            property_uri.startswith("sc-domain:")
            or property_uri.startswith("http://")
            or property_uri.startswith("https://")
        ):
            raise GSCConfigurationError("property_uri must be a sc-domain: or URL-prefix property")
        try:
            grain = CollectionGrain(value.get("collection_grain", "query-page"))
        except ValueError as error:
            raise GSCConfigurationError("unsupported collection_grain") from error
        search_type = value.get("search_type", "web")
        if search_type not in SUPPORTED_SEARCH_TYPES:
            raise GSCConfigurationError("Epic 2 supports search_type=web only")
        optional = value.get("optional_dimensions", [])
        if not isinstance(optional, list) or any(
            dimension not in SUPPORTED_OPTIONAL_DIMENSIONS for dimension in optional
        ):
            raise GSCConfigurationError("unsupported optional dimension")
        if len(set(optional)) != len(optional):
            raise GSCConfigurationError("optional dimensions must not be duplicated")
        auth_mode = value.get("auth_mode", "service_account")
        if auth_mode not in SUPPORTED_AUTH_MODES:
            raise GSCConfigurationError("auth_mode must be service_account or oauth")
        return cls(
            property_uri=property_uri.strip(),
            collection_grain=grain,
            search_type=search_type,
            optional_dimensions=tuple(optional),
            country=_optional_string(value.get("country"), "country"),
            device=_optional_string(value.get("device"), "device"),
            auth_mode=auth_mode,
        )

    def as_json(self) -> dict[str, Any]:
        return {
            "property_uri": self.property_uri,
            "collection_grain": self.collection_grain.value,
            "search_type": self.search_type,
            "optional_dimensions": list(self.optional_dimensions),
            "country": self.country,
            "device": self.device,
            "auth_mode": self.auth_mode,
        }


def _optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise GSCConfigurationError(f"{field} must be a non-empty string or null")
    return value.strip()
