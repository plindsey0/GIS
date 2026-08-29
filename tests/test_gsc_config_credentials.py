from __future__ import annotations

import json
from pathlib import Path

import pytest

from gis.integrations.gsc.config import CollectionGrain, GSCConfigurationError, GSCConnectionConfig
from gis.integrations.gsc.credentials import CredentialResolutionError, resolve_credential


def test_valid_connection_configuration_supports_domain_property() -> None:
    config = GSCConnectionConfig.from_json(
        {
            "property_uri": "sc-domain:example.com",
            "collection_grain": "query-page",
            "search_type": "web",
            "optional_dimensions": ["country"],
        }
    )
    assert config.collection_grain is CollectionGrain.QUERY_PAGE
    assert config.dimensions == ("date", "query", "page", "country")


@pytest.mark.parametrize("value", [{}, {"property_uri": ""}, {"property_uri": "example.com"}])
def test_invalid_or_missing_property_uri_is_rejected(value: dict[str, str]) -> None:
    with pytest.raises(GSCConfigurationError):
        GSCConnectionConfig.from_json(value)


def test_credential_environment_reference_resolves_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = {"type": "service_account", "private_key": "test-only-secret"}
    monkeypatch.setenv("TEST_GSC_CREDENTIAL", json.dumps(secret))
    assert resolve_credential("env:TEST_GSC_CREDENTIAL") == secret


def test_credential_file_reference_resolves(tmp_path: Path) -> None:
    path = tmp_path / "credential.json"
    path.write_text('{"refresh_token":"test"}', encoding="utf-8")
    assert resolve_credential(f"file:{path}")["refresh_token"] == "test"


def test_credential_value_is_never_part_of_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GSC_TEST_SECRET", '{"private_key":"do-not-log"}')
    reference = "env:GSC_TEST_SECRET"
    assert "do-not-log" not in reference
    assert resolve_credential(reference)["private_key"] == "do-not-log"


def test_unsupported_credential_reference_is_rejected() -> None:
    with pytest.raises(CredentialResolutionError):
        resolve_credential("inline:secret")
