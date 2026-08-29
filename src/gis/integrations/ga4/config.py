from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class GA4ConfigurationError(ValueError):
    pass


class GA4Dataset(str, enum.Enum):
    LANDING_PAGE = "landing-page"
    ACQUISITION = "acquisition"
    EVENTS = "events"


ALL_DATASETS = tuple(GA4Dataset)
SUPPORTED_AUTH_MODES = ("service_account", "oauth")


@dataclass(frozen=True)
class GA4ConnectionConfig:
    property_id: str
    auth_mode: str = "service_account"
    default_datasets: tuple[GA4Dataset, ...] = ALL_DATASETS
    property_timezone: str | None = None

    @property
    def property_resource(self) -> str:
        return f"properties/{self.property_id}"

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> GA4ConnectionConfig:
        raw_property = value.get("property_id")
        if not isinstance(raw_property, str):
            raw_property = str(raw_property) if raw_property is not None else ""
        property_id = raw_property.removeprefix("properties/").strip()
        if not property_id.isdigit() or int(property_id) <= 0:
            raise GA4ConfigurationError("configuration_json.property_id must be numeric")
        auth_mode = value.get("auth_mode", "service_account")
        if auth_mode not in SUPPORTED_AUTH_MODES:
            raise GA4ConfigurationError("auth_mode must be service_account or oauth")
        raw_datasets = value.get("default_datasets", [item.value for item in ALL_DATASETS])
        if not isinstance(raw_datasets, list) or not raw_datasets:
            raise GA4ConfigurationError("default_datasets must be a non-empty list")
        try:
            datasets = tuple(GA4Dataset(item) for item in raw_datasets)
        except (ValueError, TypeError) as error:
            raise GA4ConfigurationError("unsupported GA4 dataset") from error
        if len(set(datasets)) != len(datasets):
            raise GA4ConfigurationError("default_datasets must not contain duplicates")
        timezone_name = value.get("property_timezone")
        if timezone_name is not None:
            if not isinstance(timezone_name, str) or not timezone_name:
                raise GA4ConfigurationError("property_timezone must be an IANA timezone")
            try:
                ZoneInfo(timezone_name)
            except ZoneInfoNotFoundError as error:
                raise GA4ConfigurationError("property_timezone must be an IANA timezone") from error
        return cls(property_id, auth_mode, datasets, timezone_name)

    def as_json(self) -> dict[str, Any]:
        return {
            "property_id": self.property_id,
            "auth_mode": self.auth_mode,
            "default_datasets": [item.value for item in self.default_datasets],
            "property_timezone": self.property_timezone,
        }
