from __future__ import annotations

import hmac

from gis.integrations.gsc.credentials import CredentialResolutionError, resolve_credential


def authorize(reference: str | None, supplied_key: str) -> None:
    credential = resolve_credential(reference)
    expected = credential.get("write_key")
    if not isinstance(expected, str) or not expected:
        raise CredentialResolutionError("telemetry credential requires write_key")
    if not hmac.compare_digest(expected, supplied_key):
        raise PermissionError("invalid telemetry write key")
