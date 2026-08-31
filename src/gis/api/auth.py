from __future__ import annotations

import hmac
import os
from enum import Enum
from typing import Optional

from fastapi import Header

from gis.api.errors import ApiError


class Role(str, Enum):
    READ = "READ"
    REVIEW = "REVIEW"
    APPROVE = "APPROVE"
    ADMIN = "ADMIN"


ROLE_ORDER = {Role.READ: 0, Role.REVIEW: 1, Role.APPROVE: 2, Role.ADMIN: 3}


def require_role(required: Role):  # type: ignore[no-untyped-def]
    def dependency(
        x_gis_operator_key: Optional[str] = Header(default=None),
        x_gis_role: Role = Header(default=Role.READ),
    ) -> str:
        configured = os.environ.get("GIS_API_OPERATOR_KEY")
        if not configured:
            raise ApiError(
                503,
                "AUTH_NOT_CONFIGURED",
                "Operator authentication is not configured.",
                retryable=False,
            )
        if not x_gis_operator_key or not hmac.compare_digest(x_gis_operator_key, configured):
            raise ApiError(401, "AUTH_REQUIRED", "Valid operator authentication is required.")
        if ROLE_ORDER[x_gis_role] < ROLE_ORDER[required]:
            raise ApiError(403, "ROLE_REQUIRED", f"The {required.value} role is required.")
        return x_gis_role.value

    return dependency
