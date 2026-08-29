from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from google.auth.credentials import Credentials
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuthCredentials

from gis.integrations.gsc.config import GSCConfigurationError

READONLY_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


class CredentialResolutionError(RuntimeError):
    pass


def resolve_credential(reference: str | None) -> dict[str, Any]:
    if not reference:
        raise CredentialResolutionError("credential_reference is required")
    if reference.startswith("env:"):
        variable = reference.removeprefix("env:")
        raw = os.environ.get(variable)
        if raw is None:
            raise CredentialResolutionError(f"credential environment variable {variable} is unset")
    elif reference.startswith("file:"):
        path = Path(reference.removeprefix("file:")).expanduser()
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as error:
            raise CredentialResolutionError("credential file cannot be read") from error
    else:
        raise CredentialResolutionError("credential_reference must use env: or file:")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CredentialResolutionError("credential value is not valid JSON") from error
    if not isinstance(value, dict):
        raise CredentialResolutionError("credential JSON must be an object")
    return value


def build_credentials(
    auth_mode: str, info: dict[str, Any], scopes: list[str] | None = None
) -> Credentials:
    requested_scopes = scopes or [READONLY_SCOPE]
    if auth_mode == "service_account":
        try:
            return service_account.Credentials.from_service_account_info(  # type: ignore[no-any-return,no-untyped-call]
                info, scopes=requested_scopes
            )
        except (ValueError, KeyError) as error:
            raise CredentialResolutionError("invalid service-account credential JSON") from error
    if auth_mode == "oauth":
        required = ("refresh_token", "client_id", "client_secret")
        if any(not info.get(field) for field in required):
            raise CredentialResolutionError(
                "OAuth credential JSON requires refresh_token, client_id, and client_secret"
            )
        return OAuthCredentials(  # type: ignore[no-untyped-call]
            token=None,
            refresh_token=str(info["refresh_token"]),
            token_uri=str(info.get("token_uri", "https://oauth2.googleapis.com/token")),
            client_id=str(info["client_id"]),
            client_secret=str(info["client_secret"]),
            scopes=requested_scopes,
        )
    raise GSCConfigurationError("unsupported auth_mode")


def authorized_session(
    auth_mode: str, reference: str | None, scopes: list[str] | None = None
) -> AuthorizedSession:
    return AuthorizedSession(  # type: ignore[no-untyped-call]
        build_credentials(auth_mode, resolve_credential(reference), scopes)
    )
