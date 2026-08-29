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
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    records_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[Optional[str]] = mapped_column(Text)
    source_cursor: Mapped[Optional[str]] = mapped_column(Text)
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
