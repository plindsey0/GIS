from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

SCHEMA = "gis_core"
RAW_SCHEMA = "gis_raw"


class TenantStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"


class SiteStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class DomainType(str, enum.Enum):
    PRIMARY = "PRIMARY"
    ALIAS = "ALIAS"
    REDIRECT = "REDIRECT"
    COMPETITOR = "COMPETITOR"
    RELATED = "RELATED"
    OTHER = "OTHER"


class SourceType(str, enum.Enum):
    FIRST_PARTY = "FIRST_PARTY"
    PUBLIC = "PUBLIC"
    COMMERCIAL = "COMMERCIAL"
    CUSTOMER_CONNECTED = "CUSTOMER_CONNECTED"
    CRAWLED = "CRAWLED"
    MANUAL = "MANUAL"


class RightsDecision(str, enum.Enum):
    ALLOWED = "ALLOWED"
    PROHIBITED = "PROHIBITED"
    UNKNOWN = "UNKNOWN"


class RightsStatus(str, enum.Enum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"


class PermittedUse(str, enum.Enum):
    INTERNAL_ANALYSIS = "internal_analysis"
    COMMERCIAL_USE = "commercial_use"
    RAW_RETENTION = "raw_retention"
    NORMALIZED_RETENTION = "normalized_retention"
    DERIVATIVE_CREATION = "derivative_creation"
    AGGREGATE_STATISTICS = "aggregate_statistics"
    EXTERNAL_PUBLICATION = "external_publication"
    RAW_REDISTRIBUTION = "raw_redistribution"
    NORMALIZED_REDISTRIBUTION = "normalized_redistribution"
    CUSTOMER_FACING_DISPLAY = "customer_facing_display"
    CUSTOMER_EXPORT = "customer_export"
    RAG_RETRIEVAL = "rag_retrieval"
    AI_INFERENCE = "ai_inference"
    AI_TRAINING = "ai_training"


class AcquisitionMethod(str, enum.Enum):
    FIRST_PARTY = "FIRST_PARTY"
    PUBLIC_API = "PUBLIC_API"
    AUTHENTICATED_API = "AUTHENTICATED_API"
    LICENSED_API = "LICENSED_API"
    OPEN_DATA = "OPEN_DATA"
    PUBLIC_WEB = "PUBLIC_WEB"
    USER_PROVIDED = "USER_PROVIDED"
    MANUAL_IMPORT = "MANUAL_IMPORT"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class AssetType(str, enum.Enum):
    TABLE = "TABLE"
    VIEW = "VIEW"
    MODEL = "MODEL"
    DATASET = "DATASET"
    METRIC = "METRIC"
    EVIDENCE = "EVIDENCE"
    OTHER = "OTHER"


class AssetLayer(str, enum.Enum):
    RAW = "RAW"
    CORE = "CORE"
    STAGING = "STAGING"
    INTERMEDIATE = "INTERMEDIATE"
    ANALYTICS = "ANALYTICS"
    EXTERNAL = "EXTERNAL"
    OTHER = "OTHER"


class LineageType(str, enum.Enum):
    TRANSFORMS = "TRANSFORMS"
    REFERENCES = "REFERENCES"
    DERIVES = "DERIVES"


class SerpFeatureType(str, enum.Enum):
    ORGANIC = "ORGANIC"
    PAID = "PAID"
    FEATURED_SNIPPET = "FEATURED_SNIPPET"
    AI_ANSWER = "AI_ANSWER"
    PEOPLE_ALSO_ASK = "PEOPLE_ALSO_ASK"
    LOCAL_PACK = "LOCAL_PACK"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    SHOPPING = "SHOPPING"
    KNOWLEDGE_PANEL = "KNOWLEDGE_PANEL"
    NEWS = "NEWS"
    DISCUSSION_FORUM = "DISCUSSION_FORUM"
    RELATED_SEARCH = "RELATED_SEARCH"
    SITELINK = "SITELINK"
    MAP = "MAP"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class ResultOwnership(str, enum.Enum):
    OWN_SITE = "OWN_SITE"
    KNOWN_COMPETITOR = "KNOWN_COMPETITOR"
    OTHER = "OTHER"


class ExperienceMeasurementType(str, enum.Enum):
    FIELD = "FIELD"
    LAB = "LAB"


class ExperienceScope(str, enum.Enum):
    URL = "URL"
    ORIGIN = "ORIGIN"


class FormFactor(str, enum.Enum):
    MOBILE = "MOBILE"
    DESKTOP = "DESKTOP"
    TABLET = "TABLET"
    ALL = "ALL"
    UNKNOWN = "UNKNOWN"


class ExperienceAvailability(str, enum.Enum):
    DATA_AVAILABLE = "DATA_AVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    FAILED = "FAILED"


class ExperienceMetric(str, enum.Enum):
    LCP = "LCP"
    INP = "INP"
    CLS = "CLS"
    FCP = "FCP"
    TTFB = "TTFB"
    PERFORMANCE_SCORE = "PERFORMANCE_SCORE"
    ACCESSIBILITY_SCORE = "ACCESSIBILITY_SCORE"
    BEST_PRACTICES_SCORE = "BEST_PRACTICES_SCORE"
    SEO_SCORE = "SEO_SCORE"


class ConnectionType(str, enum.Enum):
    NATIVE = "NATIVE"
    BYOD = "BYOD"
    LICENSED_ENRICHMENT = "LICENSED_ENRICHMENT"
    CUSTOMER_SIDE = "CUSTOMER_SIDE"


class ConnectionStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    ERROR = "ERROR"


class IngestionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class QualityFlag(str, enum.Enum):
    VALID = "VALID"
    SUSPECT = "SUSPECT"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


def enum_type(enum_class: type[enum.Enum], name: str) -> Enum:
    return Enum(enum_class, name=name, schema=SCHEMA, native_enum=True)


def value_enum_type(enum_class: type[enum.Enum], name: str) -> Enum:
    return Enum(
        enum_class,
        name=name,
        schema=SCHEMA,
        native_enum=True,
        values_callable=lambda items: [str(item.value) for item in items],
    )


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProvenanceMixin:
    """Reusable columns for future typed, append-oriented observation tables."""

    source_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(512))
    observation_batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    effective_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    effective_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    quality_flag: Mapped[QualityFlag] = mapped_column(
        enum_type(QualityFlag, "quality_flag"), nullable=False, default=QualityFlag.UNKNOWN
    )
    raw_payload_reference: Mapped[Optional[str]] = mapped_column(Text)
    rights_policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    @declared_attr.directive
    def __table_args__(cls) -> tuple[Any, ...]:
        return (
            CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)"),
            CheckConstraint(
                "effective_end IS NULL OR effective_start IS NULL OR effective_end >= effective_start"
            ),
        )


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenant"
    __table_args__ = ({"schema": SCHEMA},)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[TenantStatus] = mapped_column(
        enum_type(TenantStatus, "tenant_status"), nullable=False, default=TenantStatus.ACTIVE
    )


class Organization(Base, TimestampMixin):
    __tablename__ = "organization"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_organization_tenant_slug"),
        UniqueConstraint("tenant_id", "id", name="uq_organization_tenant_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)


class Site(Base, TimestampMixin):
    __tablename__ = "site"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "organization_id"],
            [f"{SCHEMA}.organization.tenant_id", f"{SCHEMA}.organization.id"],
            ondelete="CASCADE",
            name="fk_site_organization_tenant",
        ),
        UniqueConstraint("tenant_id", "slug", name="uq_site_tenant_slug"),
        UniqueConstraint("tenant_id", "id", name="uq_site_tenant_id"),
        UniqueConstraint("public_id", name="uq_site_public_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    status: Mapped[SiteStatus] = mapped_column(
        enum_type(SiteStatus, "site_status"), nullable=False, default=SiteStatus.ACTIVE
    )


class Domain(Base, TimestampMixin):
    __tablename__ = "domain"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            ondelete="CASCADE",
            name="fk_domain_site_tenant",
        ),
        UniqueConstraint("tenant_id", "site_id", "hostname", name="uq_domain_site_hostname"),
        Index("ix_domain_hostname", "hostname"),
        Index(
            "uq_domain_primary_per_site",
            "site_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    hostname: Mapped[str] = mapped_column(String(253), nullable=False)
    domain_type: Mapped[DomainType] = mapped_column(
        enum_type(DomainType, "domain_type"), nullable=False, default=DomainType.OTHER
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class DataRightsPolicy(Base, TimestampMixin):
    __tablename__ = "data_rights_policy"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_rights_policy_tenant_id"),
        CheckConstraint(
            "retention_days IS NULL OR retention_days >= 0", name="ck_policy_retention"
        ),
        Index("ix_data_rights_policy_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    commercial_use_allowed: Mapped[RightsDecision] = mapped_column(
        enum_type(RightsDecision, "rights_decision"), nullable=False, default=RightsDecision.UNKNOWN
    )
    third_party_processing_allowed: Mapped[RightsDecision] = mapped_column(
        enum_type(RightsDecision, "rights_decision"), nullable=False, default=RightsDecision.UNKNOWN
    )
    deterministic_analysis_allowed: Mapped[RightsDecision] = mapped_column(
        enum_type(RightsDecision, "rights_decision"), nullable=False, default=RightsDecision.UNKNOWN
    )
    ai_inference_allowed: Mapped[RightsDecision] = mapped_column(
        enum_type(RightsDecision, "rights_decision"), nullable=False, default=RightsDecision.UNKNOWN
    )
    model_training_allowed: Mapped[RightsDecision] = mapped_column(
        enum_type(RightsDecision, "rights_decision"), nullable=False, default=RightsDecision.UNKNOWN
    )
    raw_storage_allowed: Mapped[RightsDecision] = mapped_column(
        enum_type(RightsDecision, "rights_decision"), nullable=False, default=RightsDecision.UNKNOWN
    )
    derived_storage_allowed: Mapped[RightsDecision] = mapped_column(
        enum_type(RightsDecision, "rights_decision"), nullable=False, default=RightsDecision.UNKNOWN
    )
    retention_days: Mapped[Optional[int]] = mapped_column(Integer)
    raw_display_allowed: Mapped[RightsDecision] = mapped_column(
        enum_type(RightsDecision, "rights_decision"), nullable=False, default=RightsDecision.UNKNOWN
    )
    derived_display_allowed: Mapped[RightsDecision] = mapped_column(
        enum_type(RightsDecision, "rights_decision"), nullable=False, default=RightsDecision.UNKNOWN
    )
    aggregation_allowed: Mapped[RightsDecision] = mapped_column(
        enum_type(RightsDecision, "rights_decision"), nullable=False, default=RightsDecision.UNKNOWN
    )
    cross_tenant_learning_allowed: Mapped[RightsDecision] = mapped_column(
        enum_type(RightsDecision, "rights_decision"), nullable=False, default=RightsDecision.UNKNOWN
    )
    attribution_required: Mapped[RightsDecision] = mapped_column(
        enum_type(RightsDecision, "rights_decision"), nullable=False, default=RightsDecision.UNKNOWN
    )
    attribution_text: Mapped[Optional[str]] = mapped_column(Text)
    license_type: Mapped[Optional[str]] = mapped_column(String(100))
    license_version: Mapped[Optional[str]] = mapped_column(String(100))
    license_url: Mapped[Optional[str]] = mapped_column(String(2048))
    license_review_date: Mapped[Optional[date]] = mapped_column(Date)
    policy_notes: Mapped[Optional[str]] = mapped_column(Text)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False, default="1")
    effective_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    review_authority: Mapped[Optional[str]] = mapped_column(String(255))
    documented_basis: Mapped[Optional[str]] = mapped_column(Text)
    jurisdiction_notes: Mapped[Optional[str]] = mapped_column(Text)
    supersedes_policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id", ondelete="SET NULL")
    )


class DataRightsGrant(Base, TimestampMixin):
    __tablename__ = "data_rights_grant"
    __table_args__ = (
        UniqueConstraint("policy_id", "permitted_use", name="uq_rights_grant_policy_use"),
        Index("ix_rights_grant_policy", "policy_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.data_rights_policy.id", ondelete="CASCADE"),
        nullable=False,
    )
    permitted_use: Mapped[PermittedUse] = mapped_column(
        value_enum_type(PermittedUse, "permitted_use"), nullable=False
    )
    status: Mapped[RightsStatus] = mapped_column(
        enum_type(RightsStatus, "rights_status"), nullable=False, default=RightsStatus.UNKNOWN
    )
    reason: Mapped[Optional[str]] = mapped_column(Text)


class DataSource(Base, TimestampMixin):
    __tablename__ = "data_source"
    __table_args__ = ({"schema": SCHEMA},)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        enum_type(SourceType, "source_type"), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    default_rights_policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id", ondelete="SET NULL")
    )
    acquisition_method: Mapped[AcquisitionMethod] = mapped_column(
        enum_type(AcquisitionMethod, "acquisition_method"),
        nullable=False,
        default=AcquisitionMethod.UNKNOWN,
    )
    authoritative_url: Mapped[Optional[str]] = mapped_column(String(2048))
    terms_url: Mapped[Optional[str]] = mapped_column(String(2048))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DataSourceConnection(Base, TimestampMixin):
    __tablename__ = "data_source_connection"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            name="fk_connection_site_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "rights_policy_id"],
            [
                f"{SCHEMA}.data_rights_policy.tenant_id",
                f"{SCHEMA}.data_rights_policy.id",
            ],
            name="fk_connection_rights_policy_tenant",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_connection_tenant_id"),
        UniqueConstraint("tenant_id", "site_id", "id", name="uq_connection_tenant_site_id"),
        Index("ix_connection_tenant_site", "tenant_id", "site_id"),
        Index("ix_data_source_connection_tenant_id", "tenant_id"),
        Index("ix_data_source_connection_data_source_id", "data_source_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.tenant.id", ondelete="CASCADE"),
        nullable=False,
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_source.id"), nullable=False
    )
    rights_policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    connection_type: Mapped[ConnectionType] = mapped_column(
        enum_type(ConnectionType, "connection_type"), nullable=False
    )
    status: Mapped[ConnectionStatus] = mapped_column(
        enum_type(ConnectionStatus, "connection_status"),
        nullable=False,
        default=ConnectionStatus.PENDING,
    )
    external_account_id: Mapped[Optional[str]] = mapped_column(String(255))
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    credential_reference: Mapped[Optional[str]] = mapped_column(String(1024))
    last_successful_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_attempted_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class IngestionRun(Base):
    __tablename__ = "ingestion_run"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            name="fk_ingestion_site_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "data_source_connection_id"],
            [
                f"{SCHEMA}.data_source_connection.tenant_id",
                f"{SCHEMA}.data_source_connection.id",
            ],
            ondelete="CASCADE",
            name="fk_ingestion_connection_tenant",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at", name="ck_ingestion_times"
        ),
        CheckConstraint(
            "records_received >= 0 AND records_inserted >= 0 AND records_rejected >= 0 AND error_count >= 0",
            name="ck_ingestion_counts",
        ),
        Index("ix_ingestion_tenant_site", "tenant_id", "site_id"),
        Index("ix_ingestion_connection_started", "data_source_connection_id", "started_at"),
        Index("ix_ingestion_status", "status"),
        UniqueConstraint("tenant_id", "id", name="uq_ingestion_run_tenant_id"),
        UniqueConstraint("tenant_id", "site_id", "id", name="uq_ingestion_run_tenant_site_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    data_source_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[IngestionStatus] = mapped_column(
        enum_type(IngestionStatus, "ingestion_status"),
        nullable=False,
        default=IngestionStatus.PENDING,
    )
    records_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[Optional[str]] = mapped_column(Text)
    source_cursor: Mapped[Optional[str]] = mapped_column(Text)
    rights_policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id", ondelete="SET NULL")
    )
    acquisition_method: Mapped[AcquisitionMethod] = mapped_column(
        enum_type(AcquisitionMethod, "acquisition_method"),
        nullable=False,
        default=AcquisitionMethod.UNKNOWN,
    )
    collector_name: Mapped[Optional[str]] = mapped_column(String(255))
    collector_version: Mapped[Optional[str]] = mapped_column(String(100))
    schema_version: Mapped[Optional[str]] = mapped_column(String(100))
    requested_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    requested_end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DataAsset(Base, TimestampMixin):
    __tablename__ = "data_asset"
    __table_args__ = (
        UniqueConstraint("canonical_name", name="uq_data_asset_canonical_name"),
        Index("ix_data_asset_layer", "layer"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(String(512), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(
        enum_type(AssetType, "asset_type"), nullable=False
    )
    layer: Mapped[AssetLayer] = mapped_column(enum_type(AssetLayer, "asset_layer"), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class DataAssetSource(Base, TimestampMixin):
    __tablename__ = "data_asset_source"
    __table_args__ = (
        UniqueConstraint(
            "asset_id", "data_source_id", "data_source_connection_id", name="uq_asset_source_scope"
        ),
        Index("ix_data_asset_source_asset", "asset_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.data_asset.id", ondelete="CASCADE"),
        nullable=False,
    )
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.data_source.id", ondelete="CASCADE"),
        nullable=False,
    )
    data_source_connection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_source_connection.id", ondelete="CASCADE")
    )
    rights_policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id", ondelete="SET NULL")
    )


class DataAssetLineage(Base):
    __tablename__ = "data_asset_lineage"
    __table_args__ = (
        CheckConstraint("upstream_asset_id <> downstream_asset_id", name="ck_lineage_not_self"),
        UniqueConstraint("upstream_asset_id", "downstream_asset_id", name="uq_asset_lineage_edge"),
        Index("ix_lineage_downstream", "downstream_asset_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    upstream_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.data_asset.id", ondelete="CASCADE"),
        nullable=False,
    )
    downstream_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.data_asset.id", ondelete="CASCADE"),
        nullable=False,
    )
    lineage_type: Mapped[LineageType] = mapped_column(
        enum_type(LineageType, "lineage_type"), nullable=False, default=LineageType.TRANSFORMS
    )
    transformation_reference: Mapped[Optional[str]] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class GSCSearchObservation(Base):
    """Versioned Google Search Console Search Analytics observation."""

    __tablename__ = "gsc_search_observation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            name="fk_gsc_observation_site_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "data_source_connection_id"],
            [
                f"{SCHEMA}.data_source_connection.tenant_id",
                f"{SCHEMA}.data_source_connection.id",
            ],
            name="fk_gsc_observation_connection_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "ingestion_run_id"],
            [
                f"{SCHEMA}.ingestion_run.tenant_id",
                f"{SCHEMA}.ingestion_run.site_id",
                f"{SCHEMA}.ingestion_run.id",
            ],
            name="fk_gsc_observation_run_tenant_site",
        ),
        CheckConstraint("clicks >= 0", name="ck_gsc_clicks_nonnegative"),
        CheckConstraint("impressions >= 0", name="ck_gsc_impressions_nonnegative"),
        CheckConstraint("ctr >= 0", name="ck_gsc_ctr_nonnegative"),
        CheckConstraint("position >= 0", name="ck_gsc_position_nonnegative"),
        CheckConstraint(
            "effective_end IS NULL OR effective_end >= effective_start",
            name="ck_gsc_effective_window",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_gsc_confidence",
        ),
        Index("ix_gsc_tenant_site_date", "tenant_id", "site_id", "observed_date"),
        Index("ix_gsc_connection_date", "data_source_connection_id", "observed_date"),
        Index("ix_gsc_observed_date", "observed_date"),
        Index("ix_gsc_page_hash", "page_hash"),
        Index("ix_gsc_query_hash", "query_hash"),
        Index("ix_gsc_observation_key", "observation_key"),
        Index("ix_gsc_ingestion_run", "ingestion_run_id"),
        Index(
            "uq_gsc_current_observation",
            "observation_key",
            unique=True,
            postgresql_where=text("effective_end IS NULL"),
        ),
        {"schema": RAW_SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data_source_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rights_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.data_rights_policy.id"),
        nullable=False,
    )
    source_record_id: Mapped[Optional[str]] = mapped_column(String(512))
    observation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    collection_grain: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_date: Mapped[date] = mapped_column(Date, nullable=False)
    query: Mapped[Optional[str]] = mapped_column(Text)
    query_hash: Mapped[Optional[str]] = mapped_column(String(64))
    page: Mapped[Optional[str]] = mapped_column(Text)
    page_hash: Mapped[Optional[str]] = mapped_column(String(64))
    country: Mapped[Optional[str]] = mapped_column(String(16))
    device: Mapped[Optional[str]] = mapped_column(String(32))
    search_appearance: Mapped[Optional[str]] = mapped_column(String(255))
    search_type: Mapped[str] = mapped_column(String(32), nullable=False)
    clicks: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    impressions: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    ctr: Mapped[Decimal] = mapped_column(Numeric(20, 12), nullable=False)
    position: Mapped[Decimal] = mapped_column(Numeric(20, 12), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    effective_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    quality_flag: Mapped[QualityFlag] = mapped_column(
        enum_type(QualityFlag, "quality_flag"), nullable=False, default=QualityFlag.VALID
    )
    raw_payload_reference: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


def _ga4_table_args(prefix: str, extras: tuple[Any, ...]) -> tuple[Any, ...]:
    return (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            name=f"fk_{prefix}_site_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "data_source_connection_id"],
            [
                f"{SCHEMA}.data_source_connection.tenant_id",
                f"{SCHEMA}.data_source_connection.id",
            ],
            name=f"fk_{prefix}_connection_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "ingestion_run_id"],
            [
                f"{SCHEMA}.ingestion_run.tenant_id",
                f"{SCHEMA}.ingestion_run.site_id",
                f"{SCHEMA}.ingestion_run.id",
            ],
            name=f"fk_{prefix}_run_tenant_site",
        ),
        CheckConstraint(
            "effective_end IS NULL OR effective_end >= effective_start",
            name=f"ck_{prefix}_effective_window",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=f"ck_{prefix}_confidence",
        ),
        Index(f"ix_{prefix}_tenant_site_date", "tenant_id", "site_id", "observed_date"),
        Index(f"ix_{prefix}_connection_date", "data_source_connection_id", "observed_date"),
        Index(f"ix_{prefix}_observation_key", "observation_key"),
        Index(f"ix_{prefix}_ingestion_run", "ingestion_run_id"),
        Index(
            f"uq_{prefix}_current_observation",
            "observation_key",
            unique=True,
            postgresql_where=text("effective_end IS NULL"),
        ),
        *extras,
        {"schema": RAW_SCHEMA},
    )


class GA4ObservationMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data_source_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rights_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.data_rights_policy.id"),
        nullable=False,
    )
    source_record_id: Mapped[Optional[str]] = mapped_column(String(512))
    observation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_date: Mapped[date] = mapped_column(Date, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    effective_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    quality_flag: Mapped[QualityFlag] = mapped_column(
        enum_type(QualityFlag, "quality_flag"), nullable=False, default=QualityFlag.VALID
    )
    raw_payload_reference: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class GA4LandingPageObservation(GA4ObservationMixin, Base):
    __tablename__ = "ga4_landing_page_observation"
    __table_args__ = _ga4_table_args(
        "ga4_landing",
        (
            Index("ix_ga4_landing_page_hash", "landing_page_hash"),
            *(
                CheckConstraint(f"{name} >= 0", name=f"ck_ga4_landing_{name}_nonnegative")
                for name in (
                    "sessions",
                    "active_users",
                    "new_users",
                    "engaged_sessions",
                    "engagement_rate",
                    "average_session_duration",
                    "event_count",
                    "key_events",
                )
            ),
            CheckConstraint("engagement_rate <= 1", name="ck_ga4_landing_engagement_rate_max"),
        ),
    )
    landing_page: Mapped[str] = mapped_column(Text, nullable=False)
    landing_page_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    session_default_channel_group: Mapped[str] = mapped_column(String(255), nullable=False)
    session_source: Mapped[str] = mapped_column(Text, nullable=False)
    session_medium: Mapped[str] = mapped_column(Text, nullable=False)
    device_category: Mapped[str] = mapped_column(String(64), nullable=False)
    country: Mapped[str] = mapped_column(String(255), nullable=False)
    sessions: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    active_users: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    new_users: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    engaged_sessions: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    engagement_rate: Mapped[Decimal] = mapped_column(Numeric(20, 12), nullable=False)
    average_session_duration: Mapped[Decimal] = mapped_column(Numeric(20, 12), nullable=False)
    event_count: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    key_events: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)


class GA4AcquisitionObservation(GA4ObservationMixin, Base):
    __tablename__ = "ga4_acquisition_observation"
    __table_args__ = _ga4_table_args(
        "ga4_acquisition",
        (
            Index("ix_ga4_acquisition_channel", "session_default_channel_group"),
            Index("ix_ga4_acquisition_source_hash", "source_hash"),
            Index("ix_ga4_acquisition_medium_hash", "medium_hash"),
            *(
                CheckConstraint(f"{name} >= 0", name=f"ck_ga4_acquisition_{name}_nonnegative")
                for name in (
                    "sessions",
                    "active_users",
                    "new_users",
                    "engaged_sessions",
                    "engagement_rate",
                    "event_count",
                    "key_events",
                )
            ),
            CheckConstraint("engagement_rate <= 1", name="ck_ga4_acquisition_engagement_rate_max"),
        ),
    )
    session_default_channel_group: Mapped[str] = mapped_column(String(255), nullable=False)
    session_source: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    session_medium: Mapped[str] = mapped_column(Text, nullable=False)
    medium_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    session_campaign: Mapped[str] = mapped_column(Text, nullable=False)
    device_category: Mapped[str] = mapped_column(String(64), nullable=False)
    country: Mapped[str] = mapped_column(String(255), nullable=False)
    sessions: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    active_users: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    new_users: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    engaged_sessions: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    engagement_rate: Mapped[Decimal] = mapped_column(Numeric(20, 12), nullable=False)
    event_count: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    key_events: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)


class GA4EventObservation(GA4ObservationMixin, Base):
    __tablename__ = "ga4_event_observation"
    __table_args__ = _ga4_table_args(
        "ga4_event",
        (
            Index("ix_ga4_event_name_hash", "event_name_hash"),
            *(
                CheckConstraint(f"{name} >= 0", name=f"ck_ga4_event_{name}_nonnegative")
                for name in (
                    "event_count",
                    "total_users",
                    "event_count_per_user",
                    "key_events",
                )
            ),
        ),
    )
    event_name: Mapped[str] = mapped_column(Text, nullable=False)
    event_name_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    landing_page: Mapped[str] = mapped_column(Text, nullable=False)
    page_path: Mapped[str] = mapped_column(Text, nullable=False)
    session_default_channel_group: Mapped[str] = mapped_column(String(255), nullable=False)
    device_category: Mapped[str] = mapped_column(String(64), nullable=False)
    country: Mapped[str] = mapped_column(String(255), nullable=False)
    event_count: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    total_users: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    event_count_per_user: Mapped[Decimal] = mapped_column(Numeric(20, 12), nullable=False)
    key_events: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)


class ProductSession(Base, TimestampMixin):
    __tablename__ = "session"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            name="fk_session_site_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "data_source_connection_id"],
            [
                f"{SCHEMA}.data_source_connection.tenant_id",
                f"{SCHEMA}.data_source_connection.site_id",
                f"{SCHEMA}.data_source_connection.id",
            ],
            name="fk_session_connection_scope",
        ),
        UniqueConstraint("tenant_id", "site_id", "session_key", name="uq_session_scope_key"),
        UniqueConstraint("tenant_id", "site_id", "id", name="uq_session_scope_id"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_session_end_time"),
        Index("ix_session_tenant_site_started", "tenant_id", "site_id", "started_at"),
        Index("ix_session_anonymous_visitor", "anonymous_visitor_key"),
        Index("ix_session_landing_path", "landing_path"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data_source_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rights_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id"), nullable=False
    )
    session_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    landing_url: Mapped[Optional[str]] = mapped_column(String(2048))
    landing_path: Mapped[Optional[str]] = mapped_column(String(2048))
    referrer_url: Mapped[Optional[str]] = mapped_column(String(2048))
    initial_utm_source: Mapped[Optional[str]] = mapped_column(String(255))
    initial_utm_medium: Mapped[Optional[str]] = mapped_column(String(255))
    initial_utm_campaign: Mapped[Optional[str]] = mapped_column(String(255))
    initial_utm_term: Mapped[Optional[str]] = mapped_column(String(255))
    initial_utm_content: Mapped[Optional[str]] = mapped_column(String(255))
    initial_gclid: Mapped[Optional[str]] = mapped_column(String(512))
    initial_msclkid: Mapped[Optional[str]] = mapped_column(String(512))
    initial_referrer_domain: Mapped[Optional[str]] = mapped_column(String(253))
    device_category: Mapped[Optional[str]] = mapped_column(String(64))
    browser_family: Mapped[Optional[str]] = mapped_column(String(128))
    os_family: Mapped[Optional[str]] = mapped_column(String(128))
    country_code: Mapped[Optional[str]] = mapped_column(String(2))
    region_code: Mapped[Optional[str]] = mapped_column(String(16))
    anonymous_visitor_key: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))


class CalculatorRun(Base, TimestampMixin):
    __tablename__ = "calculator_run"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            name="fk_calculator_run_site_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "session_id"],
            [f"{SCHEMA}.session.tenant_id", f"{SCHEMA}.session.site_id", f"{SCHEMA}.session.id"],
            name="fk_calculator_run_session_scope",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "data_source_connection_id"],
            [
                f"{SCHEMA}.data_source_connection.tenant_id",
                f"{SCHEMA}.data_source_connection.site_id",
                f"{SCHEMA}.data_source_connection.id",
            ],
            name="fk_calculator_run_connection_scope",
        ),
        UniqueConstraint(
            "tenant_id", "site_id", "calculator_run_key", name="uq_calculator_run_scope_key"
        ),
        UniqueConstraint("tenant_id", "site_id", "id", name="uq_calculator_run_scope_id"),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at", name="ck_calculator_run_times"
        ),
        CheckConstraint("recalculation_count >= 0", name="ck_calculator_run_recalculation_count"),
        Index("ix_calculator_run_tenant_site_started", "tenant_id", "site_id", "started_at"),
        Index("ix_calculator_run_type", "calculator_type"),
        Index("ix_calculator_run_session", "session_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data_source_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rights_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id"), nullable=False
    )
    calculator_run_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    calculator_type: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    initial_page_path: Mapped[Optional[str]] = mapped_column(String(2048))
    input_schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    result_schema_version: Mapped[Optional[str]] = mapped_column(String(100))
    input_bucket_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    result_bucket_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    recalculation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ProductEvent(Base):
    __tablename__ = "event"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            name="fk_event_site_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "session_id"],
            [f"{SCHEMA}.session.tenant_id", f"{SCHEMA}.session.site_id", f"{SCHEMA}.session.id"],
            name="fk_event_session_scope",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "calculator_run_id"],
            [
                f"{SCHEMA}.calculator_run.tenant_id",
                f"{SCHEMA}.calculator_run.site_id",
                f"{SCHEMA}.calculator_run.id",
            ],
            name="fk_event_calculator_run_scope",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "data_source_connection_id"],
            [
                f"{SCHEMA}.data_source_connection.tenant_id",
                f"{SCHEMA}.data_source_connection.site_id",
                f"{SCHEMA}.data_source_connection.id",
            ],
            name="fk_event_connection_scope",
        ),
        UniqueConstraint("tenant_id", "site_id", "event_id", name="uq_event_scope_id"),
        UniqueConstraint("tenant_id", "site_id", "id", name="uq_event_internal_scope_id"),
        CheckConstraint("event_version > 0", name="ck_event_version_positive"),
        Index("ix_event_tenant_site_occurred", "tenant_id", "site_id", "occurred_at"),
        Index("ix_event_session_occurred", "session_id", "occurred_at"),
        Index("ix_event_name_occurred", "event_name", "occurred_at"),
        Index("ix_event_page_path", "page_path"),
        Index("ix_event_calculator_run", "calculator_run_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    calculator_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    data_source_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rights_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id"), nullable=False
    )
    ingestion_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.ingestion_run.id", name="fk_event_ingestion_run"),
    )
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    page_url: Mapped[Optional[str]] = mapped_column(String(2048))
    page_path: Mapped[Optional[str]] = mapped_column(String(2048))
    event_properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    sequence_number: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TelemetryTransportBatch(Base):
    """Operational usage/provenance record; transport details never enter event properties."""

    __tablename__ = "telemetry_transport_batch"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            name="fk_telemetry_batch_site_tenant",
        ),
        CheckConstraint(
            "events_received >= 0 AND events_accepted >= 0 AND events_rejected >= 0 "
            "AND duplicates_ignored >= 0 AND payload_bytes >= 0",
            name="ck_telemetry_batch_counters",
        ),
        UniqueConstraint(
            "transport", "transport_message_id", name="uq_telemetry_transport_message"
        ),
        UniqueConstraint("site_id", "batch_id", name="uq_telemetry_site_batch"),
        Index("ix_telemetry_batch_site_processed", "site_id", "processed_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.ingestion_run.id"), nullable=False
    )
    transport: Mapped[str] = mapped_column(String(32), nullable=False)
    transport_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    events_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events_accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates_ignored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Conversion(Base):
    __tablename__ = "conversion"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            name="fk_conversion_site_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "session_id"],
            [f"{SCHEMA}.session.tenant_id", f"{SCHEMA}.session.site_id", f"{SCHEMA}.session.id"],
            name="fk_conversion_session_scope",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "calculator_run_id"],
            [
                f"{SCHEMA}.calculator_run.tenant_id",
                f"{SCHEMA}.calculator_run.site_id",
                f"{SCHEMA}.calculator_run.id",
            ],
            name="fk_conversion_calculator_run_scope",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "source_event_id"],
            [f"{SCHEMA}.event.tenant_id", f"{SCHEMA}.event.site_id", f"{SCHEMA}.event.id"],
            name="fk_conversion_source_event_scope",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "data_source_connection_id"],
            [
                f"{SCHEMA}.data_source_connection.tenant_id",
                f"{SCHEMA}.data_source_connection.site_id",
                f"{SCHEMA}.data_source_connection.id",
            ],
            name="fk_conversion_connection_scope",
        ),
        UniqueConstraint("tenant_id", "site_id", "conversion_id", name="uq_conversion_scope_id"),
        Index("ix_conversion_tenant_site_occurred", "tenant_id", "site_id", "occurred_at"),
        Index("ix_conversion_type_occurred", "conversion_type", "occurred_at"),
        Index("ix_conversion_session", "session_id"),
        Index("ix_conversion_calculator_run", "calculator_run_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    calculator_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    data_source_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rights_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id"), nullable=False
    )
    conversion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    conversion_type: Mapped[str] = mapped_column(String(100), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    conversion_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    currency: Mapped[Optional[str]] = mapped_column(String(3))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TrackedQuery(Base, TimestampMixin):
    __tablename__ = "tracked_query"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "tenant_id",
            "site_id",
            "normalized_query",
            "search_engine",
            "country_code",
            "location_code",
            "language_code",
            "device",
            name="uq_tracked_query_context",
        ),
        CheckConstraint(
            "requested_depth > 0 AND requested_depth <= 1000", name="ck_tracked_query_depth"
        ),
        Index("ix_tracked_query_normalized", "normalized_query"),
        Index("ix_tracked_query_tenant_site_active", "tenant_id", "site_id", "active"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="STANDARD")
    cadence: Mapped[str] = mapped_column(String(32), nullable=False, default="WEEKLY")
    device: Mapped[str] = mapped_column(String(32), nullable=False, default="desktop")
    search_engine: Mapped[str] = mapped_column(String(32), nullable=False, default="google")
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    location_code: Mapped[Optional[int]] = mapped_column(Integer)
    location_name: Mapped[Optional[str]] = mapped_column(String(255))
    language_code: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    requested_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)


class SerpObservation(Base):
    __tablename__ = "serp_observation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "ingestion_run_id"],
            [
                f"{SCHEMA}.ingestion_run.tenant_id",
                f"{SCHEMA}.ingestion_run.site_id",
                f"{SCHEMA}.ingestion_run.id",
            ],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "data_source_connection_id"],
            [f"{SCHEMA}.data_source_connection.tenant_id", f"{SCHEMA}.data_source_connection.id"],
        ),
        CheckConstraint(
            "effective_end IS NULL OR effective_end >= effective_start",
            name="ck_serp_effective_window",
        ),
        Index("ix_serp_query_date", "tracked_query_id", "observed_date"),
        Index("ix_serp_ingestion_run", "ingestion_run_id"),
        Index(
            "uq_serp_current_observation",
            "observation_key",
            unique=True,
            postgresql_where=text("effective_end IS NULL"),
        ),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tracked_query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tracked_query.id"), nullable=False
    )
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data_source_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rights_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id"), nullable=False
    )
    rights_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_task_id: Mapped[Optional[str]] = mapped_column(String(255))
    observation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_date: Mapped[date] = mapped_column(Date, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    search_engine: Mapped[str] = mapped_column(String(32), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    location_code: Mapped[Optional[int]] = mapped_column(Integer)
    location_name: Mapped[Optional[str]] = mapped_column(String(255))
    language_code: Mapped[str] = mapped_column(String(16), nullable=False)
    device: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SerpResult(Base):
    __tablename__ = "serp_result"
    __table_args__ = (
        UniqueConstraint(
            "serp_observation_id",
            "rank_absolute",
            "provider_type",
            name="uq_serp_result_position_type",
        ),
        CheckConstraint("rank_absolute > 0", name="ck_serp_result_rank"),
        Index("ix_serp_result_observation", "serp_observation_id"),
        Index("ix_serp_result_domain", "hostname"),
        Index("ix_serp_result_url", "normalized_url"),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    serp_observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.serp_observation.id", ondelete="CASCADE"),
        nullable=False,
    )
    rank_absolute: Mapped[int] = mapped_column(Integer, nullable=False)
    rank_group: Mapped[Optional[int]] = mapped_column(Integer)
    feature_type: Mapped[SerpFeatureType] = mapped_column(
        enum_type(SerpFeatureType, "serp_feature_type"), nullable=False
    )
    provider_type: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text)
    normalized_url: Mapped[Optional[str]] = mapped_column(Text)
    hostname: Mapped[Optional[str]] = mapped_column(String(253))
    title: Mapped[Optional[str]] = mapped_column(Text)
    snippet: Mapped[Optional[str]] = mapped_column(Text)
    breadcrumb: Mapped[Optional[str]] = mapped_column(Text)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_organic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_feature: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ownership: Mapped[ResultOwnership] = mapped_column(
        enum_type(ResultOwnership, "result_ownership"),
        nullable=False,
        default=ResultOwnership.OTHER,
    )
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ExternalSearchObservation(Base):
    __tablename__ = "external_search_observation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "ingestion_run_id"],
            [
                f"{SCHEMA}.ingestion_run.tenant_id",
                f"{SCHEMA}.ingestion_run.site_id",
                f"{SCHEMA}.ingestion_run.id",
            ],
        ),
        CheckConstraint(
            "effective_end IS NULL OR effective_end >= effective_start",
            name="ck_external_search_effective_window",
        ),
        Index("ix_external_search_target_date", "target_domain", "observed_date"),
        Index("ix_external_search_run", "ingestion_run_id"),
        Index(
            "uq_external_search_current",
            "observation_key",
            unique=True,
            postgresql_where=text("effective_end IS NULL"),
        ),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data_source_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_source_connection.id"), nullable=False
    )
    rights_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id"), nullable=False
    )
    rights_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    observation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_domain: Mapped[str] = mapped_column(String(253), nullable=False)
    country_code: Mapped[Optional[str]] = mapped_column(String(2))
    location_code: Mapped[Optional[int]] = mapped_column(Integer)
    location_name: Mapped[Optional[str]] = mapped_column(String(255))
    language_code: Mapped[str] = mapped_column(String(16), nullable=False)
    device: Mapped[Optional[str]] = mapped_column(String(32))
    observed_date: Mapped[date] = mapped_column(Date, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_task_id: Mapped[Optional[str]] = mapped_column(String(255))
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    items_returned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_reported_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    cost_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    effective_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ExternalKeywordRanking(Base):
    __tablename__ = "external_keyword_ranking"
    __table_args__ = (
        UniqueConstraint(
            "external_search_observation_id",
            "normalized_keyword",
            "ranking_domain",
            "normalized_url",
            name="uq_external_keyword_observation_rank",
        ),
        CheckConstraint("position > 0", name="ck_external_keyword_position"),
        Index("ix_external_keyword_normalized", "normalized_keyword"),
        Index("ix_external_keyword_domain", "ranking_domain"),
        Index("ix_external_keyword_url", "normalized_url"),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_search_observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.external_search_observation.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_keyword: Mapped[str] = mapped_column(Text, nullable=False)
    ranking_domain: Mapped[str] = mapped_column(String(253), nullable=False)
    ranking_url: Mapped[Optional[str]] = mapped_column(Text)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    prior_position: Mapped[Optional[int]] = mapped_column(Integer)
    ranking_type: Mapped[str] = mapped_column(String(100), nullable=False, default="organic")
    search_volume: Mapped[Optional[int]] = mapped_column(Integer)
    cpc: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    paid_competition: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    competition_index: Mapped[Optional[int]] = mapped_column(Integer)
    search_intent: Mapped[Optional[str]] = mapped_column(String(100))
    keyword_difficulty: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    estimated_traffic: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    estimated_traffic_share: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    monthly_searches: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    metric_semantics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ExternalCompetitorObservation(Base):
    __tablename__ = "external_competitor_observation"
    __table_args__ = (
        UniqueConstraint(
            "external_search_observation_id",
            "competitor_domain",
            name="uq_external_competitor_observation_domain",
        ),
        Index("ix_external_competitor_domain", "competitor_domain"),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_search_observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.external_search_observation.id", ondelete="CASCADE"),
        nullable=False,
    )
    competitor_domain: Mapped[str] = mapped_column(String(253), nullable=False)
    target_keyword_count: Mapped[Optional[int]] = mapped_column(Integer)
    competitor_keyword_count: Mapped[Optional[int]] = mapped_column(Integer)
    shared_keyword_count: Mapped[Optional[int]] = mapped_column(Integer)
    provider_relevance: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    provider_estimated_traffic: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    provider_visibility: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    gis_competitive_strength: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    metric_semantics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ExperienceObservation(Base):
    __tablename__ = "experience_observation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "ingestion_run_id"],
            [
                f"{SCHEMA}.ingestion_run.tenant_id",
                f"{SCHEMA}.ingestion_run.site_id",
                f"{SCHEMA}.ingestion_run.id",
            ],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "data_source_connection_id"],
            [f"{SCHEMA}.data_source_connection.tenant_id", f"{SCHEMA}.data_source_connection.id"],
        ),
        CheckConstraint("metric_value IS NULL OR metric_value >= 0", name="ck_experience_value"),
        CheckConstraint(
            "good_proportion IS NULL OR good_proportion BETWEEN 0 AND 1", name="ck_experience_good"
        ),
        CheckConstraint(
            "needs_improvement_proportion IS NULL OR needs_improvement_proportion BETWEEN 0 AND 1",
            name="ck_experience_needs",
        ),
        CheckConstraint(
            "poor_proportion IS NULL OR poor_proportion BETWEEN 0 AND 1", name="ck_experience_poor"
        ),
        Index("ix_experience_target_period", "normalized_target", "period_end"),
        Index("ix_experience_ingestion_run", "ingestion_run_id"),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data_source_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rights_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id"), nullable=False
    )
    rights_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_start: Mapped[Optional[date]] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_target: Mapped[str] = mapped_column(Text, nullable=False)
    measurement_type: Mapped[ExperienceMeasurementType] = mapped_column(
        enum_type(ExperienceMeasurementType, "experience_measurement_type"), nullable=False
    )
    scope: Mapped[ExperienceScope] = mapped_column(
        enum_type(ExperienceScope, "experience_scope"), nullable=False
    )
    form_factor: Mapped[FormFactor] = mapped_column(
        enum_type(FormFactor, "experience_form_factor"), nullable=False
    )
    availability: Mapped[ExperienceAvailability] = mapped_column(
        enum_type(ExperienceAvailability, "experience_availability"), nullable=False
    )
    metric: Mapped[ExperienceMetric] = mapped_column(
        enum_type(ExperienceMetric, "experience_metric"), nullable=False
    )
    metric_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    unit: Mapped[Optional[str]] = mapped_column(String(32))
    percentile: Mapped[Optional[int]] = mapped_column(Integer)
    classification: Mapped[Optional[str]] = mapped_column(String(32))
    good_proportion: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 8))
    needs_improvement_proportion: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 8))
    poor_proportion: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 8))
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
