from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    limit: int
    total: int


class SiteContext(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    slug: str
    canonical_url: str
    timezone: str
    status: str


class OpportunitySummary(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    site_id: uuid.UUID
    title: str
    family: str
    opportunity_type: str
    status: str
    priority: str
    evidence_sufficiency: str
    entity_id: uuid.UUID
    entity_type: str
    entity_key: str
    detected_at: datetime
    updated_at: datetime
    materiality: dict[str, Any]
    limitations: list[str]
    recommendation_status: Optional[str] = None
    intervention_status: Optional[str] = None


class DecisionInput(BaseModel):
    actor: str = Field(min_length=1, max_length=255)
    reason: Optional[str] = Field(default=None, max_length=2000)
    expected_updated_at: Optional[datetime] = None


class RecommendationReviewInput(DecisionInput):
    candidate_ids: list[uuid.UUID] = Field(default_factory=list)


class ResourceDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID
    tenant_id: Optional[uuid.UUID] = None
    site_id: Optional[uuid.UUID] = None
    resource_type: str
    data: dict[str, Any]


class Health(BaseModel):
    status: str
    database: str
    auth_configured: bool
    api_version: str
    request_id: uuid.UUID


class GenerationInput(BaseModel):
    dry_run: bool = False
    force: bool = False


class StatusInput(DecisionInput):
    pass
