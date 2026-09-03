"""One secret resolution path for collectors and execution-readiness probes.

Probes never authenticate to an external provider and never return secret values.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
from collections.abc import Mapping
from pathlib import Path

from gis.models import FailureCategory
from gis.orchestration.reliability import ClassifiedFailure


class CredentialUnavailable(ClassifiedFailure):
    def __init__(self, invalid: bool = False) -> None:
        super().__init__(
            FailureCategory.CONFIGURATION_ERROR,
            "CREDENTIAL_INVALID_CONFIGURATION"
            if invalid
            else "CREDENTIAL_UNAVAILABLE: configured credential cannot be resolved by the execution worker",
        )


def dataforseo_credentials(
    reference: str | None,
    *,
    environment: Mapping[str, str] | None = None,
    secret_file: Path | None = None,
) -> tuple[str, str]:
    env = os.environ if environment is None else environment
    if not reference or not reference.startswith("env:") or not reference[4:].isidentifier():
        raise CredentialUnavailable(invalid=True)
    key = reference[4:]
    raw = env.get(key)
    values: dict[str, str] = dict(env)
    if not raw and key in {"GIS_DATAFORSEO_CREDENTIAL", "DATAFORSEO_CREDENTIAL_JSON"}:
        path = secret_file or Path.home() / ".config/gis/secrets/dataforseo.env"
        if not (values.get("DATAFORSEO_LOGIN") and values.get("DATAFORSEO_PASSWORD")):
            try:
                if (
                    path.is_symlink()
                    or path.stat().st_mode & 0o077
                    or path.stat().st_uid != os.getuid()
                ):
                    raise CredentialUnavailable(invalid=True)
                for line in path.read_text(encoding="utf-8").splitlines():
                    line = line.strip().removeprefix("export ")
                    if not line or line.startswith("#"):
                        continue
                    name, separator, value = line.partition("=")
                    if separator and name.strip() in {
                        key,
                        "DATAFORSEO_LOGIN",
                        "DATAFORSEO_PASSWORD",
                    }:
                        parts = shlex.split(value, comments=True)
                        if len(parts) != 1:
                            raise CredentialUnavailable(invalid=True)
                        if not values.get(name.strip()):
                            values[name.strip()] = parts[0]
            except FileNotFoundError:
                pass
            except (OSError, ValueError) as exc:
                raise CredentialUnavailable(invalid=True) from exc
        raw = values.get(key)
        if not raw and values.get("DATAFORSEO_LOGIN") and values.get("DATAFORSEO_PASSWORD"):
            return values["DATAFORSEO_LOGIN"], values["DATAFORSEO_PASSWORD"]
    if not raw:
        raise CredentialUnavailable()
    try:
        payload = json.loads(raw)
        login, password = payload["login"], payload["password"]
        if not isinstance(login, str) or not isinstance(password, str) or not login or not password:
            raise ValueError("invalid shape")
        return login, password
    except (ValueError, KeyError, TypeError) as exc:
        raise CredentialUnavailable(invalid=True) from exc


def probe(reference: str | None) -> dict[str, str]:
    try:
        dataforseo_credentials(reference)
        state = "CONNECTED_AND_RESOLVABLE"
    except CredentialUnavailable as exc:
        state = (
            "INVALID_CONFIGURATION"
            if "INVALID_CONFIGURATION" in str(exc)
            else "CONNECTED_CREDENTIAL_UNAVAILABLE"
        )
    return {
        "state": state,
        "reference_fingerprint": hashlib.sha256((reference or "").encode()).hexdigest(),
    }
