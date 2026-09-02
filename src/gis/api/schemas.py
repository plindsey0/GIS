from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
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


class GoalCreateInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)
    objective_type: str
    rationale: Optional[str] = Field(default=None, max_length=5000)
    priority: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    deadline: Optional[date] = None
    actor: str = Field(min_length=1, max_length=255)
    activate: bool = False


class GoalUpdateInput(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)
    rationale: Optional[str] = Field(default=None, max_length=5000)
    priority: Optional[str] = Field(default=None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    deadline: Optional[date] = None
    actor: str = Field(min_length=1, max_length=255)
    reason: Optional[str] = Field(default=None, max_length=2000)


class GoalTargetInput(BaseModel):
    metric_key: str = Field(min_length=1, max_length=100)
    family: str
    direction: str
    target_value: Optional[Decimal] = None
    target_upper_value: Optional[Decimal] = None
    condition: dict[str, Any] = Field(default_factory=dict)
    unit: Optional[str] = Field(default=None, max_length=100)
    actor: str = Field(min_length=1, max_length=255)


class GoalRelationshipInput(BaseModel):
    target_objective_id: uuid.UUID
    relationship_type: str = "SUPPORTS"
    actor: str = Field(min_length=1, max_length=255)


class TargetOverrideInput(BaseModel):
    value: Decimal
    actor: str = Field(min_length=1, max_length=255)
    rationale: str = Field(min_length=1, max_length=2000)


class ProviderPolicyInput(BaseModel):
    actor: str = Field(min_length=1, max_length=255)
    reason: Optional[str] = Field(default=None, max_length=2000)
    data_source_connection_id: Optional[uuid.UUID] = None
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    daily_soft_budget: Optional[Decimal] = Field(default=None, ge=0)
    daily_hard_budget: Optional[Decimal] = Field(default=None, ge=0)
    monthly_soft_budget: Optional[Decimal] = Field(default=None, ge=0)
    monthly_hard_budget: Optional[Decimal] = Field(default=None, ge=0)
    per_run_hard_budget: Optional[Decimal] = Field(default=None, ge=0)
    daily_request_limit: Optional[int] = Field(default=None, ge=0)
    monthly_request_limit: Optional[int] = Field(default=None, ge=0)
    per_run_request_limit: Optional[int] = Field(default=None, ge=0)
    allow_unknown_cost: bool = False
    timezone: str = "UTC"


class ProviderActionInput(DecisionInput):
    action: str = Field(pattern="^(ENABLE|DISABLE|PAUSE|RESUME)$")


class ProviderCapabilityInput(BaseModel):
    actor: str = Field(min_length=1, max_length=255)
    enabled: bool
    cadence: str = Field(pattern="^(MANUAL_ONLY|DAILY|WEEKLY|MONTHLY|CUSTOM_INTERVAL)$")


class ProviderTargetInput(BaseModel):
    actor: str = Field(min_length=1, max_length=255)
    target_type: str = Field(pattern="^(QUERY|DOMAIN|URL|MARKET|SITE|CUSTOM)$")
    target_value: str = Field(min_length=1, max_length=2000)
    priority: str = Field(default="STANDARD", pattern="^(LOW|STANDARD|HIGH|CRITICAL)$")


class ProviderTargetStatusInput(BaseModel):
    actor: str = Field(min_length=1, max_length=255)
    enabled: bool


class ProviderPreflightInput(BaseModel):
    capability_key: str = Field(min_length=1, max_length=100)
    target_values: list[str] = Field(default_factory=list, max_length=1000)
    estimated_requests: int = Field(ge=0)
    estimated_units: Decimal = Field(ge=0)
    reserve: bool = False
