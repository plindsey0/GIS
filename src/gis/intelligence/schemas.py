from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class OpportunityType(str, enum.Enum):
    SEO = "SEO"
    CONTENT = "CONTENT"
    CONVERSION = "CONVERSION"
    UX = "UX"
    PRODUCT = "PRODUCT"
    DATA = "DATA"
    PERFORMANCE = "PERFORMANCE"
    ACQUISITION = "ACQUISITION"
    RETENTION = "RETENTION"
    MONETIZATION = "MONETIZATION"
    OTHER = "OTHER"


class Priority(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Effort(str, enum.Enum):
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"
    UNKNOWN = "UNKNOWN"


class EvidenceItem(BaseModel):
    evidence_id: uuid.UUID
    evidence_type: str
    evidence_key: str
    source: Optional[str] = None
    source_record_id: Optional[uuid.UUID] = None
    observed_period_start: date
    observed_period_end: date
    subject: str
    description: str
    provenance: dict[str, object]


class EvidenceReference(BaseModel):
    reference_id: uuid.UUID
    reference_type: str
    packet_section: str
    evidence_package_ids: list[uuid.UUID] = Field(min_length=1)


class EvidencePacket(BaseModel):
    tenant_id: uuid.UUID
    site_id: uuid.UUID
    site: str
    generated_at: datetime
    evidence: list[EvidenceItem] = Field(min_length=1, max_length=50)
    constraints: list[str]
    construction_mode: str = "explicit"
    analytical_entity_id: Optional[uuid.UUID] = None
    entity_context: dict[str, object] = Field(default_factory=dict)
    market_context: dict[str, object] = Field(default_factory=dict)
    demand: list[dict[str, object]] = Field(default_factory=list, max_length=4)
    organic_visibility: list[dict[str, object]] = Field(default_factory=list, max_length=5)
    search_console: list[dict[str, object]] = Field(default_factory=list, max_length=10)
    engagement: list[dict[str, object]] = Field(default_factory=list, max_length=20)
    owned_surfaces: list[dict[str, object]] = Field(default_factory=list, max_length=5)
    owned_surface_observations: list[dict[str, object]] = Field(default_factory=list, max_length=5)
    quality: list[dict[str, object]] = Field(default_factory=list, max_length=50)
    evidence_gaps: list[dict[str, object]] = Field(default_factory=list, max_length=25)
    referenceable_evidence: list[EvidenceReference] = Field(default_factory=list, max_length=160)

    @property
    def evidence_ids(self) -> set[uuid.UUID]:
        return {item.evidence_id for item in self.evidence}

    @property
    def referenceable_evidence_ids(self) -> set[uuid.UUID]:
        return {item.reference_id for item in self.referenceable_evidence}

    def backing_evidence_ids(self, reference_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        references = {item.reference_id: item for item in self.referenceable_evidence}
        return {
            evidence_id
            for reference_id in reference_ids
            for evidence_id in references[reference_id].evidence_package_ids
        }


class CandidateOpportunity(BaseModel):
    title: str = Field(min_length=3)
    summary: str = Field(min_length=3)
    opportunity_type: OpportunityType
    problem_or_signal: str = Field(min_length=3)
    reasoning: str = Field(min_length=3)
    evidence_ids: list[uuid.UUID] = Field(min_length=1)
    expected_value: str = Field(min_length=3)
    confidence: float = Field(ge=0, le=1)
    suggested_action: str = Field(min_length=3)
    assumptions: list[str]
    limitations: list[str]


class OpportunityOutput(BaseModel):
    opportunities: list[CandidateOpportunity] = Field(min_length=1, max_length=5)


class CandidateRecommendation(BaseModel):
    title: str = Field(min_length=3)
    summary: str = Field(min_length=3)
    recommended_action: str = Field(min_length=3)
    rationale: str = Field(min_length=3)
    opportunity_ids: list[uuid.UUID] = Field(min_length=1)
    evidence_ids: list[uuid.UUID] = Field(min_length=1)
    expected_impact: str = Field(min_length=3)
    confidence: float = Field(ge=0, le=1)
    priority: Priority
    estimated_effort: Effort
    risks: list[str]
    dependencies: list[str]
    assumptions: list[str]
    success_signals: list[str] = Field(min_length=1)


class RecommendationOutput(BaseModel):
    recommendations: list[CandidateRecommendation] = Field(min_length=1, max_length=3)


class ExperimentProposalOutput(BaseModel):
    title: str = Field(min_length=3)
    recommendation_id: uuid.UUID
    objective: str = Field(min_length=3)
    hypothesis: str = Field(min_length=3)
    target_surface: str = Field(min_length=1)
    target_url_or_resource: str = Field(min_length=1)
    control_description: str = Field(min_length=3)
    treatment_description: str = Field(min_length=3)
    implementation_steps: list[str] = Field(min_length=1)
    primary_metric: str = Field(min_length=1)
    secondary_metrics: list[str]
    baseline_evidence_ids: list[uuid.UUID] = Field(min_length=1)
    expected_direction: str = Field(
        pattern="^(INCREASE|DECREASE|IMPROVE|MAINTAIN|NO_CHANGE|INCONCLUSIVE)$"
    )
    expected_effect_description: str = Field(min_length=3)
    evaluation_window: str = Field(min_length=3)
    minimum_observation_guidance: str = Field(min_length=3)
    guardrail_metrics: list[str] = Field(min_length=1)
    instrumentation_requirements: list[str]
    dependencies: list[str]
    risks: list[str]
    rollback_plan: str = Field(min_length=3)
    decision_rule: str = Field(min_length=3)
    implementation_notes: str = Field(min_length=3)

    @field_validator("implementation_steps", "guardrail_metrics")
    @classmethod
    def nonblank_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("items must not be blank")
        return value
