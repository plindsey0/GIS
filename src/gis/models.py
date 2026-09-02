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


class ScheduleStatus(str, enum.Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


class TriggerType(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"
    RETRY = "RETRY"
    BACKFILL = "BACKFILL"
    DEPENDENCY = "DEPENDENCY"
    CATCH_UP = "CATCH_UP"
    RECONCILIATION = "RECONCILIATION"


class OrchestrationStatus(str, enum.Enum):
    PENDING = "PENDING"
    WAITING_DEPENDENCY = "WAITING_DEPENDENCY"
    RUNNING = "RUNNING"
    RETRY_WAIT = "RETRY_WAIT"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class ObligationStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    RETRY_WAIT = "RETRY_WAIT"
    PROVIDER_DATA_PENDING = "PROVIDER_DATA_PENDING"
    SATISFIED = "SATISFIED"
    EXPIRED = "EXPIRED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class CompletionOutcome(str, enum.Enum):
    SUCCEEDED_COMPLETE = "SUCCEEDED_COMPLETE"
    SUCCEEDED_NO_DATA_EXPECTED = "SUCCEEDED_NO_DATA_EXPECTED"
    PROVIDER_DATA_PENDING = "PROVIDER_DATA_PENDING"
    PARTIAL = "PARTIAL"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    BLOCKED_RIGHTS = "BLOCKED_RIGHTS"
    BLOCKED_BUDGET = "BLOCKED_BUDGET"
    BLOCKED_CONFIGURATION = "BLOCKED_CONFIGURATION"
    ABANDONED = "ABANDONED"


class FailureCategory(str, enum.Enum):
    TRANSIENT_NETWORK = "TRANSIENT_NETWORK"
    PROVIDER_429 = "PROVIDER_429"
    PROVIDER_5XX = "PROVIDER_5XX"
    PROVIDER_DATA_PENDING = "PROVIDER_DATA_PENDING"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    RIGHTS_BLOCKED = "RIGHTS_BLOCKED"
    BUDGET_BLOCKED = "BUDGET_BLOCKED"
    INVALID_REQUEST = "INVALID_REQUEST"
    INTERNAL_PROCESSING_ERROR = "INTERNAL_PROCESSING_ERROR"
    ABANDONED_EXECUTION = "ABANDONED_EXECUTION"
    UNKNOWN_RETRYABLE = "UNKNOWN_RETRYABLE"
    UNKNOWN_TERMINAL = "UNKNOWN_TERMINAL"


class ExecutorRole(str, enum.Enum):
    SCHEDULER = "SCHEDULER"
    WORKER = "WORKER"


class ReadinessState(str, enum.Enum):
    READY = "READY"
    READY_WITH_STALE_INPUT = "READY_WITH_STALE_INPUT"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


class DependencyPolicy(str, enum.Enum):
    ALL_SUCCESS = "ALL_SUCCESS"
    ANY_SUCCESS = "ANY_SUCCESS"
    ALWAYS = "ALWAYS"


class BudgetDecision(str, enum.Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


class AlertStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class QualityFlag(str, enum.Enum):
    VALID = "VALID"
    SUSPECT = "SUSPECT"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class CompetitiveEventDomain(str, enum.Enum):
    SERP = "SERP"
    SEARCH_VISIBILITY = "SEARCH_VISIBILITY"
    CONTENT = "CONTENT"
    TECHNOLOGY = "TECHNOLOGY"
    EXPERIENCE = "EXPERIENCE"
    DOMAIN = "DOMAIN"
    CROSS_SOURCE = "CROSS_SOURCE"
    AUTHORITY = "AUTHORITY"


class CompetitiveSubjectType(str, enum.Enum):
    DOMAIN = "DOMAIN"
    PAGE = "PAGE"
    QUERY = "QUERY"
    TECHNOLOGY = "TECHNOLOGY"
    SERP_FEATURE = "SERP_FEATURE"
    CONTENT_COMPONENT = "CONTENT_COMPONENT"
    SITE = "SITE"
    COMPETITOR = "COMPETITOR"


class CompetitiveEventType(str, enum.Enum):
    SERP_RANK_ENTERED = "SERP_RANK_ENTERED"
    SERP_RANK_EXITED = "SERP_RANK_EXITED"
    SERP_RANK_INCREASED = "SERP_RANK_INCREASED"
    SERP_RANK_DECREASED = "SERP_RANK_DECREASED"
    SERP_FEATURE_APPEARED = "SERP_FEATURE_APPEARED"
    SERP_FEATURE_DISAPPEARED = "SERP_FEATURE_DISAPPEARED"
    KEYWORD_GAINED = "KEYWORD_GAINED"
    KEYWORD_LOST = "KEYWORD_LOST"
    SEARCH_VISIBILITY_INCREASED = "SEARCH_VISIBILITY_INCREASED"
    SEARCH_VISIBILITY_DECREASED = "SEARCH_VISIBILITY_DECREASED"
    PAGE_FIRST_OBSERVED = "PAGE_FIRST_OBSERVED"
    PAGE_CONTENT_CHANGED = "PAGE_CONTENT_CHANGED"
    TITLE_CHANGED = "TITLE_CHANGED"
    META_DESCRIPTION_CHANGED = "META_DESCRIPTION_CHANGED"
    HEADING_STRUCTURE_CHANGED = "HEADING_STRUCTURE_CHANGED"
    CONTENT_COMPONENT_APPEARED = "CONTENT_COMPONENT_APPEARED"
    SCHEMA_TYPE_APPEARED = "SCHEMA_TYPE_APPEARED"
    WORD_COUNT_INCREASED = "WORD_COUNT_INCREASED"
    WORD_COUNT_DECREASED = "WORD_COUNT_DECREASED"
    TECHNOLOGY_FIRST_DETECTED = "TECHNOLOGY_FIRST_DETECTED"
    TECHNOLOGY_VERSION_CHANGED = "TECHNOLOGY_VERSION_CHANGED"
    TECHNOLOGY_ADDED = "TECHNOLOGY_ADDED"
    EXPERIENCE_METRIC_IMPROVED = "EXPERIENCE_METRIC_IMPROVED"
    EXPERIENCE_METRIC_DEGRADED = "EXPERIENCE_METRIC_DEGRADED"
    COMPETITOR_PAGE_EMERGENCE = "COMPETITOR_PAGE_EMERGENCE"
    BACKLINK_FIRST_OBSERVED = "BACKLINK_FIRST_OBSERVED"
    BACKLINK_GAINED = "BACKLINK_GAINED"
    BACKLINK_LOST = "BACKLINK_LOST"
    REFERRING_DOMAIN_FIRST_OBSERVED = "REFERRING_DOMAIN_FIRST_OBSERVED"
    REFERRING_DOMAIN_GAINED = "REFERRING_DOMAIN_GAINED"
    REFERRING_DOMAIN_LOST = "REFERRING_DOMAIN_LOST"
    AUTHORITY_METRIC_INCREASED = "AUTHORITY_METRIC_INCREASED"
    AUTHORITY_METRIC_DECREASED = "AUTHORITY_METRIC_DECREASED"
    REFERRING_DOMAIN_VELOCITY_CHANGED = "REFERRING_DOMAIN_VELOCITY_CHANGED"


class EventSemanticClass(str, enum.Enum):
    MEASURED = "MEASURED"
    PROVIDER_REPORTED = "PROVIDER_REPORTED"
    GIS_DERIVED = "GIS_DERIVED"
    HEURISTIC = "HEURISTIC"


class CompetitiveEventStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    RETRACTED = "RETRACTED"


class EvidenceRole(str, enum.Enum):
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    PRIMARY = "PRIMARY"
    SUPPORTING = "SUPPORTING"


class EventRelationshipType(str, enum.Enum):
    SUPPORTS = "SUPPORTS"
    PRECEDES = "PRECEDES"
    SUPERSEDES = "SUPERSEDES"
    SAME_CHANGE = "SAME_CHANGE"
    CONSTITUENT_OF = "CONSTITUENT_OF"


class AuthorityTargetType(str, enum.Enum):
    DOMAIN = "DOMAIN"
    PAGE = "PAGE"


class AuthorityLinkState(str, enum.Enum):
    OBSERVED_ACTIVE = "OBSERVED_ACTIVE"
    OBSERVED_NEW = "OBSERVED_NEW"
    OBSERVED_LOST = "OBSERVED_LOST"
    UNKNOWN = "UNKNOWN"


class AuthorityFollowState(str, enum.Enum):
    FOLLOWED = "FOLLOWED"
    NOFOLLOW = "NOFOLLOW"
    UNKNOWN = "UNKNOWN"


class AuthorityLinkType(str, enum.Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    REDIRECT = "REDIRECT"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class AnchorClassification(str, enum.Enum):
    BRAND = "BRAND"
    EXACT_MATCH = "EXACT_MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    URL = "URL"
    GENERIC = "GENERIC"
    IMAGE_OR_EMPTY = "IMAGE_OR_EMPTY"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class MarketStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"


class MarketType(str, enum.Enum):
    SEARCH_MARKET = "SEARCH_MARKET"
    TOPIC_MARKET = "TOPIC_MARKET"
    PRODUCT_CATEGORY = "PRODUCT_CATEGORY"
    COMPETITOR_MARKET = "COMPETITOR_MARKET"
    CONTENT_MARKET = "CONTENT_MARKET"
    CUSTOM = "CUSTOM"


class MarketMemberType(str, enum.Enum):
    TRACKED_QUERY = "TRACKED_QUERY"
    QUERY_PATTERN = "QUERY_PATTERN"
    TOPIC = "TOPIC"
    DOMAIN = "DOMAIN"
    PAGE = "PAGE"
    COMPETITOR = "COMPETITOR"
    MANUAL_SEED = "MANUAL_SEED"


class MarketInclusion(str, enum.Enum):
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"


class MarketCoverageStatus(str, enum.Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    SPARSE = "SPARSE"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class MarketParticipantClass(str, enum.Enum):
    OWNED = "OWNED"
    DIRECT = "DIRECT"
    ADJACENT = "ADJACENT"
    PERIPHERAL = "PERIPHERAL"
    EMERGING = "EMERGING"
    UNKNOWN = "UNKNOWN"


class CollectionTargetType(str, enum.Enum):
    QUERY = "QUERY"
    DOMAIN = "DOMAIN"
    URL = "URL"
    TOPIC = "TOPIC"


class CollectionTargetStatus(str, enum.Enum):
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    DORMANT = "DORMANT"
    PAUSED = "PAUSED"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


class CollectionPriorityTier(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    DISCOVERY = "DISCOVERY"
    DORMANT = "DORMANT"


class CollectionCadence(str, enum.Enum):
    DAILY = "DAILY"
    MULTIPLE_PER_WEEK = "MULTIPLE_PER_WEEK"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    ON_DEMAND = "ON_DEMAND"
    NONE = "NONE"


class CollectionBlocker(str, enum.Enum):
    NONE = "NONE"
    BLOCKED_BY_RIGHTS = "BLOCKED_BY_RIGHTS"
    BUDGET_BLOCKED = "BUDGET_BLOCKED"
    NO_PROVIDER = "NO_PROVIDER"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNKNOWN_COST = "UNKNOWN_COST"
    OPERATOR_PAUSED = "OPERATOR_PAUSED"


class CollectionOverrideType(str, enum.Enum):
    FORCE_ACTIVE = "FORCE_ACTIVE"
    FORCE_PAUSED = "FORCE_PAUSED"
    FORCE_RETIRED = "FORCE_RETIRED"
    FORCE_PRIORITY = "FORCE_PRIORITY"
    FORCE_CADENCE = "FORCE_CADENCE"
    FORCE_COLLECTOR = "FORCE_COLLECTOR"


class DemandEntityType(str, enum.Enum):
    QUERY = "QUERY"
    TOPIC = "TOPIC"
    MARKET_SEGMENT = "MARKET_SEGMENT"
    MARKET = "MARKET"


class DemandSignalType(str, enum.Enum):
    FIRST_OBSERVED = "FIRST_OBSERVED"
    EMERGING = "EMERGING"
    GROWING = "GROWING"
    ACCELERATING = "ACCELERATING"
    DECELERATING = "DECELERATING"
    DECLINING = "DECLINING"
    STABLE = "STABLE"
    SPIKE = "SPIKE"
    REVERSAL = "REVERSAL"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


class DemandCoverageState(str, enum.Enum):
    OBSERVED = "OBSERVED"
    NO_DEMAND_OBSERVED = "NO_DEMAND_OBSERVED"
    NOT_OBSERVED = "NOT_OBSERVED"
    NOT_COLLECTED = "NOT_COLLECTED"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
    COLLECTION_REGIME_CHANGED = "COLLECTION_REGIME_CHANGED"
    UNKNOWN = "UNKNOWN"


class DemandEvidenceStrength(str, enum.Enum):
    INSUFFICIENT = "INSUFFICIENT"
    LIMITED = "LIMITED"
    SUPPORTED = "SUPPORTED"
    STRONGLY_SUPPORTED = "STRONGLY_SUPPORTED"


class DemandEvidenceRole(str, enum.Enum):
    PRIMARY_DEMAND_EVIDENCE = "PRIMARY_DEMAND_EVIDENCE"
    SUPPORTING_OWNED_SIGNAL = "SUPPORTING_OWNED_SIGNAL"
    SUPPORTING_COMPETITIVE_SIGNAL = "SUPPORTING_COMPETITIVE_SIGNAL"
    COLLECTION_COVERAGE_EVIDENCE = "COLLECTION_COVERAGE_EVIDENCE"


class ValidationRequestStatus(str, enum.Enum):
    OPEN = "OPEN"
    SATISFIED = "SATISFIED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class AnalyticalEntityType(str, enum.Enum):
    SITE = "SITE"
    DOMAIN = "DOMAIN"
    URL = "URL"
    QUERY = "QUERY"
    TOPIC = "TOPIC"
    MARKET = "MARKET"
    MARKET_SEGMENT = "MARKET_SEGMENT"


class IdentityRelationship(str, enum.Enum):
    SAME_ENTITY = "SAME_ENTITY"
    ALIAS_OF = "ALIAS_OF"
    CANONICAL_OF = "CANONICAL_OF"
    REDIRECTS_TO = "REDIRECTS_TO"
    SUBDOMAIN_OF = "SUBDOMAIN_OF"
    SAME_REGISTRABLE_DOMAIN = "SAME_REGISTRABLE_DOMAIN"
    MEMBER_OF = "MEMBER_OF"
    RELATED_NOT_IDENTICAL = "RELATED_NOT_IDENTICAL"


class ResolutionStrength(str, enum.Enum):
    EXACT = "EXACT"
    STRONG = "STRONG"
    SUPPORTED = "SUPPORTED"
    WEAK = "WEAK"
    UNRESOLVED = "UNRESOLVED"
    CONFLICTING = "CONFLICTING"


class AssertionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class QualityDimensionType(str, enum.Enum):
    IDENTITY_RESOLUTION = "IDENTITY_RESOLUTION"
    FRESHNESS = "FRESHNESS"
    COMPLETENESS = "COMPLETENESS"
    TEMPORAL_CONTINUITY = "TEMPORAL_CONTINUITY"
    PROVENANCE_COMPLETENESS = "PROVENANCE_COMPLETENESS"
    SOURCE_INDEPENDENCE = "SOURCE_INDEPENDENCE"
    CROSS_SOURCE_CORROBORATION = "CROSS_SOURCE_CORROBORATION"
    CONSISTENCY = "CONSISTENCY"
    METHOD_COMPATIBILITY = "METHOD_COMPATIBILITY"
    SCOPE_COMPATIBILITY = "SCOPE_COMPATIBILITY"
    RIGHTS_USABILITY = "RIGHTS_USABILITY"


class QualityDimensionState(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED = "BLOCKED"
    LIMITED = "LIMITED"
    SUPPORTED = "SUPPORTED"
    STRONG = "STRONG"


class SourceIndependenceState(str, enum.Enum):
    SAME_ROOT_SOURCE = "SAME_ROOT_SOURCE"
    DEPENDENT_DERIVATION = "DEPENDENT_DERIVATION"
    PARTIALLY_INDEPENDENT = "PARTIALLY_INDEPENDENT"
    INDEPENDENT = "INDEPENDENT"
    UNKNOWN = "UNKNOWN"


class EvidenceCompatibility(str, enum.Enum):
    COMPATIBLE = "COMPATIBLE"
    PARTIALLY_COMPATIBLE = "PARTIALLY_COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


class CorroborationState(str, enum.Enum):
    UNSUPPORTED = "UNSUPPORTED"
    SINGLE_SOURCE = "SINGLE_SOURCE"
    CORROBORATED = "CORROBORATED"
    MULTI_SOURCE_CORROBORATED = "MULTI_SOURCE_CORROBORATED"
    CONFLICTING = "CONFLICTING"
    INSUFFICIENT = "INSUFFICIENT"


class RightsUsability(str, enum.Enum):
    USABLE = "USABLE"
    BLOCKED = "BLOCKED"
    PARTIALLY_USABLE = "PARTIALLY_USABLE"
    UNKNOWN = "UNKNOWN"


class OpportunityFamily(str, enum.Enum):
    DEMAND = "DEMAND"
    VISIBILITY = "VISIBILITY"
    COMPETITIVE = "COMPETITIVE"
    CONTENT = "CONTENT"
    AUTHORITY = "AUTHORITY"
    EXPERIENCE = "EXPERIENCE"
    MARKET_STRUCTURE = "MARKET_STRUCTURE"
    INTELLIGENCE_GAP = "INTELLIGENCE_GAP"


class OpportunityStatus(str, enum.Enum):
    DETECTED = "DETECTED"
    ACTIVE = "ACTIVE"
    WATCHING = "WATCHING"
    RESOLVED = "RESOLVED"
    EXPIRED = "EXPIRED"
    DISMISSED = "DISMISSED"
    SUPERSEDED = "SUPERSEDED"


class OpportunityPriority(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    WATCH = "WATCH"


class OpportunityRelationshipType(str, enum.Enum):
    SUPPORTS = "SUPPORTS"
    RELATED_TO = "RELATED_TO"
    PARENT_OF = "PARENT_OF"
    CHILD_OF = "CHILD_OF"
    SUPERSEDES = "SUPERSEDES"


class InterventionFamily(str, enum.Enum):
    CONTENT = "CONTENT"
    SEO = "SEO"
    EXPERIENCE = "EXPERIENCE"
    CONVERSION = "CONVERSION"
    TECHNICAL = "TECHNICAL"
    INTERNAL_LINKING = "INTERNAL_LINKING"
    AUTHORITY = "AUTHORITY"
    RESEARCH_ASSET = "RESEARCH_ASSET"
    COLLECTION = "COLLECTION"


class InterventionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    MEASURING = "MEASURING"
    MEASURED = "MEASURED"
    ARCHIVED = "ARCHIVED"


class FeasibilityState(str, enum.Enum):
    FEASIBLE = "FEASIBLE"
    BLOCKED = "BLOCKED"
    PARTIALLY_FEASIBLE = "PARTIALLY_FEASIBLE"
    UNKNOWN = "UNKNOWN"


class MeasurementReadiness(str, enum.Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    NOT_READY = "NOT_READY"
    UNKNOWN = "UNKNOWN"


class MetricRole(str, enum.Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    GUARDRAIL = "GUARDRAIL"


class ExpectedDirection(str, enum.Enum):
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    IMPROVE = "IMPROVE"
    MAINTAIN = "MAINTAIN"


class ExperimentType(str, enum.Enum):
    OBSERVATIONAL_BEFORE_AFTER = "OBSERVATIONAL_BEFORE_AFTER"
    A_B_TEST = "A_B_TEST"
    HOLDOUT = "HOLDOUT"
    MATCHED_CONTROL = "MATCHED_CONTROL"
    TIME_SERIES = "TIME_SERIES"


class ExperimentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    INVALIDATED = "INVALIDATED"
    CANCELLED = "CANCELLED"


class OutcomeState(str, enum.Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_MEASURABLE = "NOT_MEASURABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class RecommendationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    VALIDATED = "VALIDATED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_ACCEPTED = "PARTIALLY_ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


class RecommendationRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    NO_VALID_RECOMMENDATION = "NO_VALID_RECOMMENDATION"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ObjectiveLevel(str, enum.Enum):
    BUSINESS = "BUSINESS"
    STRATEGIC_GROWTH = "STRATEGIC_GROWTH"
    CHANNEL_MARKET = "CHANNEL_MARKET"
    TACTICAL = "TACTICAL"


class ObjectiveType(str, enum.Enum):
    REVENUE = "REVENUE"
    PROFITABILITY = "PROFITABILITY"
    CUSTOMER_ACQUISITION = "CUSTOMER_ACQUISITION"
    LEAD_GENERATION = "LEAD_GENERATION"
    USAGE = "USAGE"
    GROWTH = "GROWTH"
    MARKET_POSITION = "MARKET_POSITION"
    RETENTION = "RETENTION"
    EFFICIENCY = "EFFICIENCY"
    CUSTOM = "CUSTOM"


class ObjectiveOrigin(str, enum.Enum):
    USER_DEFINED = "USER_DEFINED"
    DETERMINISTIC = "DETERMINISTIC"
    STATISTICAL = "STATISTICAL"
    AI_PROPOSED = "AI_PROPOSED"
    IMPORTED = "IMPORTED"
    USER_OVERRIDE = "USER_OVERRIDE"


class ObjectiveLifecycle(str, enum.Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ACHIEVED = "ACHIEVED"
    MISSED = "MISSED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class ObjectiveProgress(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    AHEAD = "AHEAD"
    ON_TRACK = "ON_TRACK"
    BEHIND = "BEHIND"
    AT_RISK = "AT_RISK"
    ACHIEVED = "ACHIEVED"
    MISSED = "MISSED"
    UNKNOWN = "UNKNOWN"


class ObjectiveMeasurementHealth(str, enum.Enum):
    MEASURABLE = "MEASURABLE"
    NOT_YET_MEASURABLE = "NOT_YET_MEASURABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    STALE_DATA = "STALE_DATA"
    BLOCKED_SOURCE = "BLOCKED_SOURCE"
    BLOCKED_RIGHTS = "BLOCKED_RIGHTS"
    UNSUPPORTED_METRIC = "UNSUPPORTED_METRIC"


class ObjectiveFeasibility(str, enum.Enum):
    NOT_ASSESSED = "NOT_ASSESSED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    PLAUSIBLE = "PLAUSIBLE"
    AGGRESSIVE = "AGGRESSIVE"
    EXTREMELY_AGGRESSIVE = "EXTREMELY_AGGRESSIVE"
    CURRENT_TRAJECTORY_INSUFFICIENT = "CURRENT_TRAJECTORY_INSUFFICIENT"
    UNSUPPORTED_BY_CURRENT_EVIDENCE = "UNSUPPORTED_BY_CURRENT_EVIDENCE"


class DecompositionState(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    BLOCKED_MISSING_DATA = "BLOCKED_MISSING_DATA"
    BLOCKED_UNSUPPORTED_METRIC = "BLOCKED_UNSUPPORTED_METRIC"
    BLOCKED_RIGHTS = "BLOCKED_RIGHTS"
    BLOCKED_STALE_DATA = "BLOCKED_STALE_DATA"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"


class ObjectiveApproval(str, enum.Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ObjectiveRelationshipType(str, enum.Enum):
    SUPPORTS = "SUPPORTS"
    DEPENDS_ON = "DEPENDS_ON"
    CONSTRAINS = "CONSTRAINS"
    CONFLICTS_WITH = "CONFLICTS_WITH"


class TargetFamily(str, enum.Enum):
    ABSOLUTE_METRIC = "ABSOLUTE_METRIC"
    RELATIVE_CHANGE = "RELATIVE_CHANGE"
    RANK = "RANK"
    COMPETITIVE = "COMPETITIVE"
    MARKET = "MARKET"
    FUNNEL = "FUNNEL"
    FINANCIAL = "FINANCIAL"
    GUARDRAIL = "GUARDRAIL"


class TargetDirection(str, enum.Enum):
    AT_LEAST = "AT_LEAST"
    AT_MOST = "AT_MOST"
    BETWEEN = "BETWEEN"
    INCREASE_BY = "INCREASE_BY"
    DECREASE_BY = "DECREASE_BY"
    RANK_AT_OR_ABOVE = "RANK_AT_OR_ABOVE"
    OUTRANK_ENTITY = "OUTRANK_ENTITY"


class DecompositionPlanStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    CANDIDATE = "CANDIDATE"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class DerivationResultStatus(str, enum.Enum):
    CURRENT = "CURRENT"
    BLOCKED = "BLOCKED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class CandidateValidationState(str, enum.Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    BLOCKED = "BLOCKED"


class RecommendationReviewDecision(str, enum.Enum):
    ACCEPT = "ACCEPT"
    PARTIAL_ACCEPT = "PARTIAL_ACCEPT"
    REJECT = "REJECT"
    REQUEST_REGENERATION = "REQUEST_REGENERATION"


class AuthorityOwnership(str, enum.Enum):
    OWNED = "OWNED"
    COMPETITOR = "COMPETITOR"
    OTHER = "OTHER"
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


class CompetitiveContentObservation(Base):
    """Immutable, revision-aware retrieval and extraction envelope."""

    __tablename__ = "competitive_content_observation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            name="fk_content_observation_site_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "ingestion_run_id"],
            [
                f"{SCHEMA}.ingestion_run.tenant_id",
                f"{SCHEMA}.ingestion_run.site_id",
                f"{SCHEMA}.ingestion_run.id",
            ],
            name="fk_content_observation_run_scope",
        ),
        CheckConstraint(
            "effective_end IS NULL OR effective_end >= effective_start",
            name="ck_content_observation_effective_window",
        ),
        Index("ix_content_observation_site_date", "tenant_id", "site_id", "observed_at"),
        Index("ix_content_observation_url", "normalized_url"),
        Index("ix_content_observation_domain", "domain"),
        Index("ix_content_observation_hash", "content_hash"),
        Index(
            "uq_content_observation_current",
            "observation_key",
            unique=True,
            postgresql_where=text("effective_end IS NULL"),
        ),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.organization.id"), nullable=False
    )
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data_source_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_source_connection.id"), nullable=False
    )
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rights_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id"), nullable=False
    )
    rights_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_url: Mapped[Optional[str]] = mapped_column(Text)
    canonical_url: Mapped[Optional[str]] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(253), nullable=False)
    page_path: Mapped[str] = mapped_column(Text, nullable=False)
    ownership_class: Mapped[str] = mapped_column(String(32), nullable=False)
    tracked_query_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tracked_query.id")
    )
    serp_result_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{RAW_SCHEMA}.serp_result.id")
    )
    external_search_observation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{RAW_SCHEMA}.external_search_observation.id")
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retrieved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    retrieval_status: Mapped[str] = mapped_column(String(50), nullable=False)
    http_status: Mapped[Optional[int]] = mapped_column(Integer)
    render_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(255))
    content_language: Mapped[Optional[str]] = mapped_column(String(32))
    response_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))
    observation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_request_id: Mapped[Optional[str]] = mapped_column(String(255))
    provider_reported_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    cost_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    raw_payload_reference: Mapped[Optional[str]] = mapped_column(Text)
    raw_retained: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retrieval_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    effective_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CompetitiveContentDocument(Base):
    __tablename__ = "competitive_content_document"
    __table_args__ = ({"schema": RAW_SCHEMA},)
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.competitive_content_observation.id", ondelete="CASCADE"),
        primary_key=True,
    )
    title: Mapped[Optional[str]] = mapped_column(Text)
    meta_description: Mapped[Optional[str]] = mapped_column(Text)
    robots_directives: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    normalized_word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    paragraph_count: Mapped[int] = mapped_column(Integer, nullable=False)
    h1_count: Mapped[int] = mapped_column(Integer, nullable=False)
    h2_count: Mapped[int] = mapped_column(Integer, nullable=False)
    h3_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ordered_list_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unordered_list_count: Mapped[int] = mapped_column(Integer, nullable=False)
    table_count: Mapped[int] = mapped_column(Integer, nullable=False)
    image_count: Mapped[int] = mapped_column(Integer, nullable=False)
    video_count: Mapped[int] = mapped_column(Integer, nullable=False)
    form_count: Mapped[int] = mapped_column(Integer, nullable=False)
    iframe_count: Mapped[int] = mapped_column(Integer, nullable=False)
    internal_link_count: Mapped[int] = mapped_column(Integer, nullable=False)
    external_link_count: Mapped[int] = mapped_column(Integer, nullable=False)
    publication_dates: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    modified_dates: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    metric_semantics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class CompetitiveContentHeading(Base):
    __tablename__ = "competitive_content_heading"
    __table_args__ = (UniqueConstraint("observation_id", "ordinal"), {"schema": RAW_SCHEMA})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.competitive_content_observation.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)


class CompetitiveContentSchemaType(Base):
    __tablename__ = "competitive_content_schema_type"
    __table_args__ = (UniqueConstraint("observation_id", "schema_type"), {"schema": RAW_SCHEMA})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.competitive_content_observation.id", ondelete="CASCADE"),
        nullable=False,
    )
    schema_type: Mapped[str] = mapped_column(String(255), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False)


class CompetitiveContentLink(Base):
    __tablename__ = "competitive_content_link"
    __table_args__ = (Index("ix_content_link_domain", "target_domain"), {"schema": RAW_SCHEMA})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.competitive_content_observation.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    target_domain: Mapped[str] = mapped_column(String(253), nullable=False)
    link_class: Mapped[str] = mapped_column(String(32), nullable=False)
    anchor_text: Mapped[Optional[str]] = mapped_column(Text)
    rel_values: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)


class CompetitiveContentComponent(Base):
    __tablename__ = "competitive_content_component"
    __table_args__ = (UniqueConstraint("observation_id", "component_type"), {"schema": RAW_SCHEMA})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.competitive_content_observation.id", ondelete="CASCADE"),
        nullable=False,
    )
    component_type: Mapped[str] = mapped_column(String(100), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    detection_method: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    metric_semantics: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class CompetitiveContentTerm(Base):
    __tablename__ = "competitive_content_term"
    __table_args__ = (
        UniqueConstraint("observation_id", "normalized_term"),
        Index("ix_content_term_normalized", "normalized_term"),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.competitive_content_observation.id", ondelete="CASCADE"),
        nullable=False,
    )
    term: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_term: Mapped[str] = mapped_column(Text, nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_semantics: Mapped[str] = mapped_column(String(32), nullable=False)


class CompetitiveContentCohort(Base, TimestampMixin):
    __tablename__ = "competitive_content_cohort"
    __table_args__ = (
        Index("ix_content_cohort_site_created", "tenant_id", "site_id", "created_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.organization.id"), nullable=False
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.site.id"), nullable=False
    )
    tracked_query_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tracked_query.id")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    frozen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CompetitiveContentCohortMember(Base):
    __tablename__ = "competitive_content_cohort_member"
    __table_args__ = (UniqueConstraint("cohort_id", "observation_id"), {"schema": SCHEMA})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.competitive_content_cohort.id", ondelete="CASCADE"),
        nullable=False,
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.competitive_content_observation.id", ondelete="RESTRICT"),
        nullable=False,
    )
    rank_position: Mapped[Optional[int]] = mapped_column(Integer)
    membership_source: Mapped[str] = mapped_column(String(50), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Technology(Base, TimestampMixin):
    __tablename__ = "technology"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_technology_slug"),
        Index("ix_technology_category", "category"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    vendor: Mapped[Optional[str]] = mapped_column(String(255))
    product_family: Mapped[Optional[str]] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class TechnologyAlias(Base, TimestampMixin):
    __tablename__ = "technology_alias"
    __table_args__ = (
        UniqueConstraint("source_key", "normalized_alias", name="uq_technology_alias_source"),
        Index("ix_technology_alias_normalized", "normalized_alias"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    technology_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.technology.id"), nullable=False
    )
    source_key: Mapped[str] = mapped_column(String(100), nullable=False)
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_identifier: Mapped[Optional[str]] = mapped_column(String(255))


class TechnologyObservation(Base):
    __tablename__ = "technology_observation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            name="fk_technology_observation_site_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "ingestion_run_id"],
            [
                f"{SCHEMA}.ingestion_run.tenant_id",
                f"{SCHEMA}.ingestion_run.site_id",
                f"{SCHEMA}.ingestion_run.id",
            ],
            name="fk_technology_observation_run_scope",
        ),
        CheckConstraint(
            "effective_end IS NULL OR effective_end >= effective_start",
            name="ck_technology_observation_effective_window",
        ),
        Index("ix_technology_observation_site_date", "tenant_id", "site_id", "observed_at"),
        Index("ix_technology_observation_domain_date", "domain", "observed_at"),
        Index(
            "uq_technology_observation_current",
            "observation_key",
            unique=True,
            postgresql_where=text("effective_end IS NULL"),
        ),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.organization.id"), nullable=False
    )
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data_source_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_source_connection.id"), nullable=False
    )
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rights_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id"), nullable=False
    )
    rights_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    domain: Mapped[str] = mapped_column(String(253), nullable=False)
    requested_url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    ownership_class: Mapped[str] = mapped_column(String(32), nullable=False)
    observation_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    collection_status: Mapped[str] = mapped_column(String(50), nullable=False)
    http_status: Mapped[Optional[int]] = mapped_column(Integer)
    render_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))
    observation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_request_id: Mapped[Optional[str]] = mapped_column(String(255))
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    provider_reported_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    cost_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    signature_version: Mapped[Optional[str]] = mapped_column(String(100))
    collection_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    effective_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TechnologyDetection(Base):
    __tablename__ = "technology_detection"
    __table_args__ = (
        UniqueConstraint(
            "observation_id",
            "technology_id",
            "detection_scope",
            name="uq_technology_detection_observation",
        ),
        Index("ix_technology_detection_technology", "technology_id"),
        Index("ix_technology_detection_semantics", "semantic_class"),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.technology_observation.id", ondelete="CASCADE"),
        nullable=False,
    )
    technology_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.technology.id"), nullable=False
    )
    provider_technology_name: Mapped[Optional[str]] = mapped_column(String(255))
    provider_category: Mapped[Optional[str]] = mapped_column(String(255))
    detected_version: Mapped[Optional[str]] = mapped_column(String(255))
    provider_first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    provider_last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    presence_status: Mapped[str] = mapped_column(String(32), nullable=False)
    detection_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    semantic_class: Mapped[str] = mapped_column(String(32), nullable=False)
    detection_method: Mapped[str] = mapped_column(String(100), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TechnologyEvidence(Base):
    __tablename__ = "technology_evidence"
    __table_args__ = (
        UniqueConstraint(
            "detection_id",
            "signature_key",
            "evidence_hash",
            name="uq_technology_evidence_signature",
        ),
        Index("ix_technology_evidence_signature", "signature_key"),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    detection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.technology_detection.id", ondelete="CASCADE"),
        nullable=False,
    )
    signature_key: Mapped[str] = mapped_column(String(255), nullable=False)
    signature_version: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    match_target: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_value: Mapped[Optional[str]] = mapped_column(Text)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    semantic_class: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
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


class AuthorityMetricDefinition(Base, TimestampMixin):
    __tablename__ = "authority_metric_definition"
    __table_args__ = (
        UniqueConstraint("provider", "metric_key", name="uq_authority_metric_provider_key"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_key: Mapped[str] = mapped_column(String(150), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    scale_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    scale_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    methodology_version: Mapped[Optional[str]] = mapped_column(String(100))
    semantic_class: Mapped[EventSemanticClass] = mapped_column(
        enum_type(EventSemanticClass, "event_semantic_class"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AuthorityObservation(Base):
    __tablename__ = "authority_observation"
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
            name="ck_authority_observation_effective_window",
        ),
        Index(
            "ix_authority_observation_target_date",
            "tenant_id",
            "site_id",
            "target_domain",
            "observed_at",
        ),
        Index("ix_authority_observation_run", "ingestion_run_id"),
        Index(
            "uq_authority_observation_current",
            "observation_key",
            unique=True,
            postgresql_where=text("effective_end IS NULL"),
        ),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.organization.id"), nullable=False
    )
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data_source_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_source_connection.id"), nullable=False
    )
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rights_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id"), nullable=False
    )
    rights_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_task_id: Mapped[Optional[str]] = mapped_column(String(255))
    target_type: Mapped[AuthorityTargetType] = mapped_column(
        enum_type(AuthorityTargetType, "authority_target_type"), nullable=False
    )
    target_domain: Mapped[str] = mapped_column(String(253), nullable=False)
    target_url: Mapped[Optional[str]] = mapped_column(Text)
    ownership: Mapped[AuthorityOwnership] = mapped_column(
        enum_type(AuthorityOwnership, "authority_ownership"), nullable=False
    )
    observed_date: Mapped[date] = mapped_column(Date, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observation_scope: Mapped[str] = mapped_column(String(100), nullable=False)
    completeness: Mapped[str] = mapped_column(String(50), nullable=False, default="UNKNOWN")
    observation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    records_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_reported_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    cost_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    effective_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuthorityMetricObservation(Base):
    __tablename__ = "authority_metric_observation"
    __table_args__ = (
        UniqueConstraint(
            "authority_observation_id",
            "metric_provider",
            "metric_key",
            name="uq_authority_metric_observation",
        ),
        CheckConstraint(
            "scale_max IS NULL OR scale_min IS NULL OR scale_max >= scale_min",
            name="ck_authority_metric_scale",
        ),
        Index("ix_authority_metric_key", "metric_provider", "metric_key"),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    authority_observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.authority_observation.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_definition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.authority_metric_definition.id")
    )
    metric_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_key: Mapped[str] = mapped_column(String(150), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    scale_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    scale_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    methodology_version: Mapped[Optional[str]] = mapped_column(String(100))
    semantic_class: Mapped[EventSemanticClass] = mapped_column(
        enum_type(EventSemanticClass, "event_semantic_class"), nullable=False
    )
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BacklinkObservation(Base):
    __tablename__ = "backlink_observation"
    __table_args__ = (
        UniqueConstraint(
            "authority_observation_id", "link_identity", name="uq_backlink_observation_identity"
        ),
        Index("ix_backlink_source_domain", "source_domain"),
        Index("ix_backlink_target_domain", "target_domain"),
        Index("ix_backlink_target_url", "target_url"),
        Index("ix_backlink_state", "link_state"),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    authority_observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.authority_observation.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_record_id: Mapped[Optional[str]] = mapped_column(String(512))
    link_identity: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_domain: Mapped[str] = mapped_column(String(253), nullable=False)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    target_domain: Mapped[str] = mapped_column(String(253), nullable=False)
    link_state: Mapped[AuthorityLinkState] = mapped_column(
        enum_type(AuthorityLinkState, "authority_link_state"), nullable=False
    )
    follow_state: Mapped[AuthorityFollowState] = mapped_column(
        enum_type(AuthorityFollowState, "authority_follow_state"), nullable=False
    )
    sponsored: Mapped[Optional[bool]] = mapped_column(Boolean)
    ugc: Mapped[Optional[bool]] = mapped_column(Boolean)
    link_type: Mapped[AuthorityLinkType] = mapped_column(
        enum_type(AuthorityLinkType, "authority_link_type"), nullable=False
    )
    anchor_text: Mapped[Optional[str]] = mapped_column(Text)
    anchor_hash: Mapped[Optional[str]] = mapped_column(String(64))
    anchor_classification: Mapped[AnchorClassification] = mapped_column(
        enum_type(AnchorClassification, "anchor_classification"), nullable=False
    )
    anchor_method: Mapped[Optional[str]] = mapped_column(String(100))
    anchor_method_version: Mapped[Optional[str]] = mapped_column(String(32))
    anchor_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    semantic_class: Mapped[EventSemanticClass] = mapped_column(
        enum_type(EventSemanticClass, "event_semantic_class"), nullable=False
    )
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ReferringDomainObservation(Base):
    __tablename__ = "referring_domain_observation"
    __table_args__ = (
        UniqueConstraint(
            "authority_observation_id", "referring_domain", name="uq_referring_domain_observation"
        ),
        Index("ix_referring_domain_target", "referring_domain", "target_domain"),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    authority_observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.authority_observation.id", ondelete="CASCADE"),
        nullable=False,
    )
    referring_domain: Mapped[str] = mapped_column(String(253), nullable=False)
    target_domain: Mapped[str] = mapped_column(String(253), nullable=False)
    backlink_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    followed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    nofollow_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    link_state: Mapped[AuthorityLinkState] = mapped_column(
        enum_type(AuthorityLinkState, "authority_link_state"), nullable=False
    )
    semantic_class: Mapped[EventSemanticClass] = mapped_column(
        enum_type(EventSemanticClass, "event_semantic_class"), nullable=False
    )
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MarketDefinition(Base, TimestampMixin):
    __tablename__ = "market_definition"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        UniqueConstraint("tenant_id", "site_id", "slug", "version", name="uq_market_version"),
        Index("ix_market_definition_scope", "tenant_id", "site_id", "slug", "status"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.organization.id"), nullable=False
    )
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[MarketStatus] = mapped_column(
        enum_type(MarketStatus, "market_status"), nullable=False
    )
    market_type: Mapped[MarketType] = mapped_column(
        enum_type(MarketType, "market_type"), nullable=False
    )
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    language_code: Mapped[str] = mapped_column(String(16), nullable=False)
    device: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    superseded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    supersedes_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.market_definition.id")
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(255))
    semantic_notes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class MarketDefinitionMember(Base):
    __tablename__ = "market_definition_member"
    __table_args__ = (
        UniqueConstraint(
            "market_definition_id", "member_type", "member_key", name="uq_market_member_identity"
        ),
        CheckConstraint("weight IS NULL OR weight >= 0", name="ck_market_member_weight"),
        Index("ix_market_member_definition", "market_definition_id", "rank_order"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.market_definition.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_type: Mapped[MarketMemberType] = mapped_column(
        enum_type(MarketMemberType, "market_member_type"), nullable=False
    )
    member_key: Mapped[str] = mapped_column(Text, nullable=False)
    member_uuid: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    inclusion: Mapped[MarketInclusion] = mapped_column(
        enum_type(MarketInclusion, "market_inclusion"), nullable=False
    )
    weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6))
    rank_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effective_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    provenance_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MarketMetricDefinition(Base, TimestampMixin):
    __tablename__ = "market_metric_definition"
    __table_args__ = (
        UniqueConstraint(
            "metric_key", "method_key", "method_version", name="uq_market_metric_method"
        ),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_key: Mapped[str] = mapped_column(String(150), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    method_key: Mapped[str] = mapped_column(String(100), nullable=False)
    method_version: Mapped[str] = mapped_column(String(50), nullable=False)
    semantic_class: Mapped[EventSemanticClass] = mapped_column(
        enum_type(EventSemanticClass, "event_semantic_class"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MarketObservation(Base):
    __tablename__ = "market_observation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        CheckConstraint("configured_query_count >= 0", name="ck_market_configured_queries"),
        CheckConstraint("observed_query_count >= 0", name="ck_market_observed_queries"),
        CheckConstraint("query_coverage_rate BETWEEN 0 AND 1", name="ck_market_query_coverage"),
        CheckConstraint(
            "effective_end IS NULL OR effective_end >= effective_start",
            name="ck_market_observation_window",
        ),
        Index("ix_market_observation_definition_date", "market_definition_id", "effective_date"),
        Index(
            "uq_market_observation_current",
            "observation_key",
            unique=True,
            postgresql_where=text("effective_end IS NULL"),
        ),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.organization.id"), nullable=False
    )
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    market_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.market_definition.id"), nullable=False
    )
    market_definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    ingestion_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.ingestion_run.id")
    )
    rights_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id"), nullable=False
    )
    rights_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    country_code: Mapped[Optional[str]] = mapped_column(String(2))
    language_code: Mapped[Optional[str]] = mapped_column(String(16))
    device: Mapped[Optional[str]] = mapped_column(String(32))
    method_key: Mapped[str] = mapped_column(String(100), nullable=False)
    method_version: Mapped[str] = mapped_column(String(50), nullable=False)
    semantic_class: Mapped[EventSemanticClass] = mapped_column(
        enum_type(EventSemanticClass, "event_semantic_class"), nullable=False
    )
    coverage_status: Mapped[MarketCoverageStatus] = mapped_column(
        enum_type(MarketCoverageStatus, "market_coverage_status"), nullable=False
    )
    configured_query_count: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_query_count: Mapped[int] = mapped_column(Integer, nullable=False)
    query_coverage_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    source_coverage: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    observation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_reported_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    cost_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    provenance_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    effective_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MarketParticipantObservation(Base):
    __tablename__ = "market_participant_observation"
    __table_args__ = (
        UniqueConstraint("market_observation_id", "domain", name="uq_market_participant_domain"),
        CheckConstraint("visibility_share BETWEEN 0 AND 1", name="ck_market_visibility_share"),
        CheckConstraint(
            "volume_weighted_visibility_share IS NULL OR volume_weighted_visibility_share BETWEEN 0 AND 1",
            name="ck_market_volume_visibility_share",
        ),
        Index("ix_market_participant_domain", "domain"),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.market_observation.id", ondelete="CASCADE"),
        nullable=False,
    )
    domain: Mapped[str] = mapped_column(String(253), nullable=False)
    ownership: Mapped[str] = mapped_column(String(32), nullable=False)
    participant_class: Mapped[MarketParticipantClass] = mapped_column(
        enum_type(MarketParticipantClass, "market_participant_class"), nullable=False
    )
    query_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ranking_page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    serp_appearance_count: Mapped[int] = mapped_column(Integer, nullable=False)
    top_3_appearances: Mapped[int] = mapped_column(Integer, nullable=False)
    top_10_appearances: Mapped[int] = mapped_column(Integer, nullable=False)
    top_20_appearances: Mapped[int] = mapped_column(Integer, nullable=False)
    visibility_weight: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    visibility_share: Mapped[Decimal] = mapped_column(Numeric(12, 10), nullable=False)
    volume_weighted_visibility: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 10))
    volume_weighted_visibility_share: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 10))
    query_overlap_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    classification_method: Mapped[str] = mapped_column(String(100), nullable=False)
    classification_version: Mapped[str] = mapped_column(String(50), nullable=False)
    semantic_class: Mapped[EventSemanticClass] = mapped_column(
        enum_type(EventSemanticClass, "event_semantic_class"), nullable=False
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class MarketSegmentObservation(Base):
    __tablename__ = "market_segment_observation"
    __table_args__ = (
        UniqueConstraint(
            "market_observation_id", "segment_type", "segment_key", name="uq_market_segment"
        ),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.market_observation.id", ondelete="CASCADE"),
        nullable=False,
    )
    segment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    segment_key: Mapped[str] = mapped_column(String(255), nullable=False)
    segment_label: Mapped[str] = mapped_column(String(255), nullable=False)
    query_count: Mapped[int] = mapped_column(Integer, nullable=False)
    participant_count: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_reported_search_volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 6))
    observed_visibility_hhi: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 10))
    method_key: Mapped[str] = mapped_column(String(100), nullable=False)
    method_version: Mapped[str] = mapped_column(String(50), nullable=False)
    semantic_class: Mapped[EventSemanticClass] = mapped_column(
        enum_type(EventSemanticClass, "event_semantic_class"), nullable=False
    )


class MarketMetricObservation(Base):
    __tablename__ = "market_metric_observation"
    __table_args__ = (
        UniqueConstraint(
            "market_observation_id",
            "metric_key",
            "method_key",
            "provider",
            name="uq_market_metric_observation",
        ),
        Index("ix_market_metric_key", "metric_key", "method_key"),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{RAW_SCHEMA}.market_observation.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_definition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.market_metric_definition.id")
    )
    metric_key: Mapped[str] = mapped_column(String(150), nullable=False)
    metric_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 10))
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="gis")
    method_key: Mapped[str] = mapped_column(String(100), nullable=False)
    method_version: Mapped[str] = mapped_column(String(50), nullable=False)
    semantic_class: Mapped[EventSemanticClass] = mapped_column(
        enum_type(EventSemanticClass, "event_semantic_class"), nullable=False
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class CollectionTarget(Base, TimestampMixin):
    __tablename__ = "collection_target"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        UniqueConstraint("tenant_id", "site_id", "identity_hash", name="uq_collection_target"),
        Index("ix_collection_target_market", "market_definition_id", "market_definition_version"),
        Index("ix_collection_target_status", "tenant_id", "site_id", "status"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    market_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.market_definition.id"), nullable=False
    )
    market_definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    target_type: Mapped[CollectionTargetType] = mapped_column(
        enum_type(CollectionTargetType, "collection_target_type"), nullable=False
    )
    normalized_identity: Mapped[str] = mapped_column(Text, nullable=False)
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    display_value: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[Optional[str]] = mapped_column(String(2))
    language_code: Mapped[Optional[str]] = mapped_column(String(16))
    device: Mapped[Optional[str]] = mapped_column(String(32))
    status: Mapped[CollectionTargetStatus] = mapped_column(
        enum_type(CollectionTargetStatus, "collection_target_status"), nullable=False
    )
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    dormant_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    human_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    current_policy_version: Mapped[Optional[str]] = mapped_column(String(100))
    provenance_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class CollectionTargetEvidence(Base):
    __tablename__ = "collection_target_evidence"
    __table_args__ = (
        UniqueConstraint(
            "target_id",
            "source_system",
            "evidence_type",
            "evidence_identifier",
            name="uq_collection_target_evidence",
        ),
        Index("ix_collection_evidence_target", "target_id", "evidence_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.collection_target.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    semantic_class: Mapped[EventSemanticClass] = mapped_column(
        enum_type(EventSemanticClass, "event_semantic_class"), nullable=False
    )
    signal_name: Mapped[str] = mapped_column(String(100), nullable=False)
    signal_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 8))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CollectionPlanningPolicy(Base, TimestampMixin):
    __tablename__ = "collection_planning_policy"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "policy_key", "policy_version", name="uq_collection_policy_version"
        ),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    policy_key: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    weights_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    thresholds_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    cadence_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class CollectorCapability(Base, TimestampMixin):
    __tablename__ = "collector_capability"
    __table_args__ = (
        UniqueConstraint("capability_key", "target_type", name="uq_collector_capability_target"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    capability_key: Mapped[str] = mapped_column(String(100), nullable=False)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.pipeline_definition.id"), nullable=False
    )
    target_type: Mapped[CollectionTargetType] = mapped_column(
        enum_type(CollectionTargetType, "collection_target_type"), nullable=False
    )
    evidence_product: Mapped[str] = mapped_column(String(100), nullable=False)
    estimated_cost_per_run: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    preference: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class CollectionPlanningRun(Base):
    __tablename__ = "collection_planning_run"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        UniqueConstraint("tenant_id", "site_id", "fingerprint", name="uq_collection_planning_run"),
        Index("ix_collection_planning_run_scope", "tenant_id", "site_id", "evaluated_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    market_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.market_definition.id"), nullable=False
    )
    market_definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.collection_planning_policy.id"), nullable=False
    )
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    target_count: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_monthly_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CollectionPlanningDecision(Base):
    __tablename__ = "collection_planning_decision"
    __table_args__ = (
        UniqueConstraint("planning_run_id", "target_id", name="uq_collection_decision_target"),
        CheckConstraint("priority_score BETWEEN 0 AND 1", name="ck_collection_priority_score"),
        Index("ix_collection_decision_target", "target_id", "evaluated_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    planning_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.collection_planning_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.collection_target.id"), nullable=False
    )
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    priority_score: Mapped[Decimal] = mapped_column(Numeric(10, 8), nullable=False)
    priority_tier: Mapped[CollectionPriorityTier] = mapped_column(
        enum_type(CollectionPriorityTier, "collection_priority_tier"), nullable=False
    )
    component_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    unknown_components: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    computed_status: Mapped[CollectionTargetStatus] = mapped_column(
        enum_type(CollectionTargetStatus, "collection_target_status"), nullable=False
    )
    effective_status: Mapped[CollectionTargetStatus] = mapped_column(
        enum_type(CollectionTargetStatus, "collection_target_status"), nullable=False
    )
    computed_cadence: Mapped[CollectionCadence] = mapped_column(
        enum_type(CollectionCadence, "collection_cadence"), nullable=False
    )
    effective_cadence: Mapped[CollectionCadence] = mapped_column(
        enum_type(CollectionCadence, "collection_cadence"), nullable=False
    )
    primary_blocker: Mapped[CollectionBlocker] = mapped_column(
        enum_type(CollectionBlocker, "collection_blocker"), nullable=False
    )
    blockers_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    override_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CollectionPlanItem(Base):
    __tablename__ = "collection_plan_item"
    __table_args__ = (
        UniqueConstraint("decision_id", "collector_capability_id", name="uq_collection_plan_item"),
        CheckConstraint("estimated_runs_month >= 0", name="ck_collection_plan_runs"),
        CheckConstraint(
            "estimated_monthly_cost IS NULL OR estimated_monthly_cost >= 0",
            name="ck_collection_plan_cost",
        ),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.collection_planning_decision.id", ondelete="CASCADE"),
        nullable=False,
    )
    collector_capability_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.collector_capability.id"), nullable=False
    )
    data_source_connection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_source_connection.id")
    )
    desired_cadence: Mapped[CollectionCadence] = mapped_column(
        enum_type(CollectionCadence, "collection_cadence"), nullable=False
    )
    effective_cadence: Mapped[CollectionCadence] = mapped_column(
        enum_type(CollectionCadence, "collection_cadence"), nullable=False
    )
    rights_status: Mapped[RightsStatus] = mapped_column(
        enum_type(RightsStatus, "rights_status"), nullable=False
    )
    budget_decision: Mapped[BudgetDecision] = mapped_column(
        enum_type(BudgetDecision, "budget_decision"), nullable=False
    )
    estimated_cost_per_run: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    estimated_runs_month: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    estimated_monthly_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    blocker: Mapped[CollectionBlocker] = mapped_column(
        enum_type(CollectionBlocker, "collection_blocker"), nullable=False
    )
    scheduled_target_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.scheduled_target.id")
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CollectionTargetOverride(Base, TimestampMixin):
    __tablename__ = "collection_target_override"
    __table_args__ = (
        Index(
            "uq_collection_override_active",
            "target_id",
            unique=True,
            postgresql_where=text("active"),
        ),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.collection_target.id", ondelete="CASCADE"),
        nullable=False,
    )
    override_type: Mapped[CollectionOverrideType] = mapped_column(
        enum_type(CollectionOverrideType, "collection_override_type"), nullable=False
    )
    forced_priority: Mapped[Optional[CollectionPriorityTier]] = mapped_column(
        enum_type(CollectionPriorityTier, "collection_priority_tier")
    )
    forced_cadence: Mapped[Optional[CollectionCadence]] = mapped_column(
        enum_type(CollectionCadence, "collection_cadence")
    )
    forced_capability_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.collector_capability.id")
    )
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cleared_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cleared_by: Mapped[Optional[str]] = mapped_column(String(255))


class DemandObservation(Base):
    __tablename__ = "demand_observation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        CheckConstraint("value IS NULL OR value >= 0", name="ck_demand_observation_value"),
        CheckConstraint(
            "effective_end IS NULL OR effective_end >= effective_start",
            name="ck_demand_observation_window",
        ),
        Index(
            "uq_demand_observation_current",
            "observation_key",
            unique=True,
            postgresql_where=text("effective_end IS NULL"),
        ),
        Index(
            "ix_demand_observation_series",
            "tenant_id",
            "site_id",
            "market_definition_id",
            "entity_key",
            "observed_date",
        ),
        {"schema": RAW_SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    market_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.market_definition.id"), nullable=False
    )
    market_definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    collection_target_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.collection_target.id")
    )
    entity_type: Mapped[DemandEntityType] = mapped_column(
        enum_type(DemandEntityType, "demand_entity_type"), nullable=False
    )
    entity_key: Mapped[str] = mapped_column(Text, nullable=False)
    observed_date: Mapped[date] = mapped_column(Date, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    source_connection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_source_connection.id")
    )
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255))
    source_metric: Mapped[str] = mapped_column(String(150), nullable=False)
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    resolution_days: Mapped[int] = mapped_column(Integer, nullable=False)
    country_code: Mapped[Optional[str]] = mapped_column(String(2))
    language_code: Mapped[Optional[str]] = mapped_column(String(16))
    device: Mapped[Optional[str]] = mapped_column(String(32))
    semantic_class: Mapped[EventSemanticClass] = mapped_column(
        enum_type(EventSemanticClass, "event_semantic_class"), nullable=False
    )
    coverage_state: Mapped[DemandCoverageState] = mapped_column(
        enum_type(DemandCoverageState, "demand_coverage_state"), nullable=False
    )
    method_key: Mapped[str] = mapped_column(String(100), nullable=False)
    method_version: Mapped[str] = mapped_column(String(50), nullable=False)
    rights_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id"), nullable=False
    )
    observation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provenance_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    effective_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DemandAnalysisRun(Base):
    __tablename__ = "demand_analysis_run"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        UniqueConstraint("tenant_id", "site_id", "fingerprint", name="uq_demand_analysis_run"),
        Index("ix_demand_analysis_scope", "tenant_id", "site_id", "analyzed_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    market_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.market_definition.id"), nullable=False
    )
    market_definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    signal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DemandSignal(Base):
    __tablename__ = "demand_signal"
    __table_args__ = (
        UniqueConstraint(
            "analysis_run_id",
            "entity_type",
            "entity_key",
            "source_series_key",
            "signal_type",
            name="uq_demand_signal_run_entity",
        ),
        Index("ix_demand_signal_entity", "collection_target_id", "window_end"),
        Index("ix_demand_signal_market", "market_definition_id", "signal_type", "window_end"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.demand_analysis_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    market_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.market_definition.id"), nullable=False
    )
    market_definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    collection_target_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.collection_target.id")
    )
    entity_type: Mapped[DemandEntityType] = mapped_column(
        enum_type(DemandEntityType, "demand_entity_type"), nullable=False
    )
    entity_key: Mapped[str] = mapped_column(Text, nullable=False)
    source_series_key: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_type: Mapped[DemandSignalType] = mapped_column(
        enum_type(DemandSignalType, "demand_signal_type"), nullable=False
    )
    window_key: Mapped[str] = mapped_column(String(20), nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    current_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    prior_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    absolute_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    relative_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8))
    velocity: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 10))
    prior_velocity: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 10))
    acceleration: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 10))
    evidence_strength: Mapped[DemandEvidenceStrength] = mapped_column(
        enum_type(DemandEvidenceStrength, "demand_evidence_strength"), nullable=False
    )
    coverage_state: Mapped[DemandCoverageState] = mapped_column(
        enum_type(DemandCoverageState, "demand_coverage_state"), nullable=False
    )
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    collection_regime_changed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    reasons_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DemandSignalEvidence(Base):
    __tablename__ = "demand_signal_evidence"
    __table_args__ = (
        UniqueConstraint("signal_id", "evidence_key", name="uq_demand_signal_evidence"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.demand_signal.id", ondelete="CASCADE"),
        nullable=False,
    )
    demand_observation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{RAW_SCHEMA}.demand_observation.id")
    )
    role: Mapped[DemandEvidenceRole] = mapped_column(
        enum_type(DemandEvidenceRole, "demand_evidence_role"), nullable=False
    )
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_key: Mapped[str] = mapped_column(String(255), nullable=False)
    semantic_class: Mapped[EventSemanticClass] = mapped_column(
        enum_type(EventSemanticClass, "event_semantic_class"), nullable=False
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DemandValidationRequest(Base, TimestampMixin):
    __tablename__ = "demand_validation_request"
    __table_args__ = (
        UniqueConstraint("identity_hash", name="uq_demand_validation_request"),
        Index("ix_demand_validation_target", "collection_target_id", "status", "expires_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.demand_signal.id", ondelete="CASCADE"),
        nullable=False,
    )
    collection_target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.collection_target.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    desired_evidence_capability: Mapped[str] = mapped_column(String(100), nullable=False)
    urgency: Mapped[CollectionPriorityTier] = mapped_column(
        enum_type(CollectionPriorityTier, "collection_priority_tier"), nullable=False
    )
    status: Mapped[ValidationRequestStatus] = mapped_column(
        enum_type(ValidationRequestStatus, "validation_request_status"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provenance_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class AnalyticalEntity(Base, TimestampMixin):
    __tablename__ = "analytical_entity"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        UniqueConstraint("tenant_id", "site_id", "identity_hash", name="uq_analytical_entity"),
        Index("ix_analytical_entity_scope", "tenant_id", "site_id", "entity_type"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_type: Mapped[AnalyticalEntityType] = mapped_column(
        enum_type(AnalyticalEntityType, "analytical_entity_type"), nullable=False
    )
    canonical_key: Mapped[str] = mapped_column(Text, nullable=False)
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[Optional[str]] = mapped_column(String(2))
    language_code: Mapped[Optional[str]] = mapped_column(String(16))
    device: Mapped[Optional[str]] = mapped_column(String(32))
    method_key: Mapped[str] = mapped_column(String(100), nullable=False)
    method_version: Mapped[str] = mapped_column(String(50), nullable=False)
    source_reference_type: Mapped[Optional[str]] = mapped_column(String(100))
    source_reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class IdentityAssertion(Base):
    __tablename__ = "identity_assertion"
    __table_args__ = (
        Index(
            "uq_identity_assertion_current",
            "assertion_hash",
            unique=True,
            postgresql_where=text("effective_end IS NULL"),
        ),
        Index("ix_identity_assertion_subject", "subject_entity_id", "relationship"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.analytical_entity.id"), nullable=False
    )
    object_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.analytical_entity.id"), nullable=False
    )
    relationship: Mapped[IdentityRelationship] = mapped_column(
        enum_type(IdentityRelationship, "identity_relationship"), nullable=False
    )
    computed_strength: Mapped[ResolutionStrength] = mapped_column(
        enum_type(ResolutionStrength, "resolution_strength"), nullable=False
    )
    effective_strength: Mapped[ResolutionStrength] = mapped_column(
        enum_type(ResolutionStrength, "resolution_strength"), nullable=False
    )
    resolution_method: Mapped[str] = mapped_column(String(100), nullable=False)
    method_version: Mapped[str] = mapped_column(String(50), nullable=False)
    assertion_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[AssertionStatus] = mapped_column(
        enum_type(AssertionStatus, "assertion_status"), nullable=False
    )
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    override_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_reason: Mapped[Optional[str]] = mapped_column(Text)
    override_actor: Mapped[Optional[str]] = mapped_column(String(255))
    effective_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvidenceContract(Base, TimestampMixin):
    __tablename__ = "evidence_contract"
    __table_args__ = (
        UniqueConstraint("contract_key", "contract_version", name="uq_evidence_contract_version"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_key: Mapped[str] = mapped_column(String(100), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirements_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EvidenceQualityRun(Base):
    __tablename__ = "evidence_quality_run"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        UniqueConstraint("tenant_id", "site_id", "fingerprint", name="uq_evidence_quality_run"),
        Index("ix_evidence_quality_run_scope", "tenant_id", "site_id", "assessed_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    method_version: Mapped[str] = mapped_column(String(50), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    input_count: Mapped[int] = mapped_column(Integer, nullable=False)
    package_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvidencePackage(Base):
    __tablename__ = "evidence_package"
    __table_args__ = (
        UniqueConstraint("identity_hash", name="uq_evidence_package_identity"),
        Index("ix_evidence_package_current", "tenant_id", "site_id", "condition_key", "period_end"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quality_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.evidence_quality_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    analytical_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.analytical_entity.id"), nullable=False
    )
    evidence_contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.evidence_contract.id"), nullable=False
    )
    demand_signal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.demand_signal.id")
    )
    market_definition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.market_definition.id")
    )
    market_definition_version: Mapped[Optional[int]] = mapped_column(Integer)
    condition_key: Mapped[str] = mapped_column(String(100), nullable=False)
    classification: Mapped[str] = mapped_column(String(100), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    sufficiency: Mapped[DemandEvidenceStrength] = mapped_column(
        enum_type(DemandEvidenceStrength, "demand_evidence_strength"), nullable=False
    )
    identity_resolution: Mapped[ResolutionStrength] = mapped_column(
        enum_type(ResolutionStrength, "resolution_strength"), nullable=False
    )
    source_independence: Mapped[SourceIndependenceState] = mapped_column(
        enum_type(SourceIndependenceState, "source_independence_state"), nullable=False
    )
    corroboration: Mapped[CorroborationState] = mapped_column(
        enum_type(CorroborationState, "corroboration_state"), nullable=False
    )
    rights_usability: Mapped[RightsUsability] = mapped_column(
        enum_type(RightsUsability, "rights_usability"), nullable=False
    )
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    independent_source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    limitations_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    method_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvidenceQualityDimension(Base):
    __tablename__ = "evidence_quality_dimension"
    __table_args__ = (
        UniqueConstraint("evidence_package_id", "dimension", name="uq_evidence_package_dimension"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.evidence_package.id", ondelete="CASCADE"),
        nullable=False,
    )
    dimension: Mapped[QualityDimensionType] = mapped_column(
        enum_type(QualityDimensionType, "quality_dimension_type"), nullable=False
    )
    state: Mapped[QualityDimensionState] = mapped_column(
        enum_type(QualityDimensionState, "quality_dimension_state"), nullable=False
    )
    method_key: Mapped[str] = mapped_column(String(100), nullable=False)
    method_version: Mapped[str] = mapped_column(String(50), nullable=False)
    observed_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    expected_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    reasons_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvidencePackageItem(Base):
    __tablename__ = "evidence_package_item"
    __table_args__ = (
        UniqueConstraint("evidence_package_id", "evidence_key", name="uq_evidence_package_item"),
        Index("ix_evidence_package_root", "evidence_package_id", "root_source_key"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.evidence_package.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_key: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    evidence_role: Mapped[str] = mapped_column(String(100), nullable=False)
    root_source_key: Mapped[Optional[str]] = mapped_column(String(100))
    independence: Mapped[SourceIndependenceState] = mapped_column(
        enum_type(SourceIndependenceState, "source_independence_state"), nullable=False
    )
    method_compatibility: Mapped[EvidenceCompatibility] = mapped_column(
        enum_type(EvidenceCompatibility, "evidence_compatibility"), nullable=False
    )
    scope_compatibility: Mapped[EvidenceCompatibility] = mapped_column(
        enum_type(EvidenceCompatibility, "evidence_compatibility"), nullable=False
    )
    rights_usability: Mapped[RightsUsability] = mapped_column(
        enum_type(RightsUsability, "rights_usability"), nullable=False
    )
    supports_claim: Mapped[Optional[bool]] = mapped_column(Boolean)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvidenceGap(Base, TimestampMixin):
    __tablename__ = "evidence_gap"
    __table_args__ = (
        UniqueConstraint("identity_hash", name="uq_evidence_gap_identity"),
        Index("ix_evidence_gap_package", "evidence_package_id", "gap_type", "resolved_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.evidence_package.id", ondelete="CASCADE"),
        nullable=False,
    )
    collection_target_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.collection_target.id")
    )
    gap_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    desired_evidence_capability: Mapped[Optional[str]] = mapped_column(String(100))
    urgency: Mapped[CollectionPriorityTier] = mapped_column(
        enum_type(CollectionPriorityTier, "collection_priority_tier"), nullable=False
    )
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    planning_evidence_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.collection_target_evidence.id")
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    provenance_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class OpportunityDetectorPolicy(Base, TimestampMixin):
    __tablename__ = "opportunity_detector_policy"
    __table_args__ = (
        UniqueConstraint(
            "detector_key", "detector_version", name="uq_opportunity_detector_version"
        ),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    detector_key: Mapped[str] = mapped_column(String(100), nullable=False)
    detector_version: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    family: Mapped[OpportunityFamily] = mapped_column(
        enum_type(OpportunityFamily, "opportunity_family"), nullable=False
    )
    opportunity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_contract_key: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    experimental: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    policy_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class Opportunity(Base, TimestampMixin):
    __tablename__ = "opportunity"
    __table_args__ = (
        UniqueConstraint("identity_hash", name="uq_opportunity_identity"),
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        Index("ix_opportunity_scope", "tenant_id", "site_id", "status", "priority"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    analytical_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.analytical_entity.id"), nullable=False
    )
    market_definition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.market_definition.id")
    )
    market_definition_version: Mapped[Optional[int]] = mapped_column(Integer)
    detector_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.opportunity_detector_policy.id"), nullable=False
    )
    family: Mapped[OpportunityFamily] = mapped_column(
        enum_type(OpportunityFamily, "opportunity_family"), nullable=False
    )
    opportunity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[OpportunityStatus] = mapped_column(
        enum_type(OpportunityStatus, "opportunity_status"), nullable=False
    )
    computed_status: Mapped[OpportunityStatus] = mapped_column(
        enum_type(OpportunityStatus, "opportunity_status"), nullable=False
    )
    priority: Mapped[OpportunityPriority] = mapped_column(
        enum_type(OpportunityPriority, "opportunity_priority"), nullable=False
    )
    evidence_sufficiency: Mapped[DemandEvidenceStrength] = mapped_column(
        enum_type(DemandEvidenceStrength, "demand_evidence_strength"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    condition_description: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    condition_first_observed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    materiality_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    priority_components_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    limitations_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)


class OpportunityEvaluation(Base):
    __tablename__ = "opportunity_evaluation"
    __table_args__ = (
        UniqueConstraint("evaluation_hash", name="uq_opportunity_evaluation"),
        Index("ix_opportunity_evaluation_history", "opportunity_id", "evaluated_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.opportunity.id", ondelete="CASCADE"),
        nullable=False,
    )
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    computed_status: Mapped[OpportunityStatus] = mapped_column(
        enum_type(OpportunityStatus, "opportunity_status"), nullable=False
    )
    qualifies: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evaluation_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reasons_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    blockers_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OpportunityEvidence(Base):
    __tablename__ = "opportunity_evidence"
    __table_args__ = (
        UniqueConstraint(
            "opportunity_evaluation_id", "evidence_package_id", name="uq_opportunity_evidence"
        ),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.opportunity_evaluation.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.evidence_package.id"), nullable=False
    )
    evidence_role: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OpportunityOverride(Base):
    __tablename__ = "opportunity_override"
    __table_args__ = (
        Index("ix_opportunity_override_current", "opportunity_id", "restored_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.opportunity.id", ondelete="CASCADE"),
        nullable=False,
    )
    dismissed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dismissed_by: Mapped[Optional[str]] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    restored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    restored_by: Mapped[Optional[str]] = mapped_column(String(255))


class InterventionTypeDefinition(Base, TimestampMixin):
    __tablename__ = "intervention_type_definition"
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_intervention_type_version"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    family: Mapped[InterventionFamily] = mapped_column(
        enum_type(InterventionFamily, "intervention_family"), nullable=False
    )
    execution_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    autonomy_level: Mapped[str] = mapped_column(
        String(50), nullable=False, default="HUMAN_APPROVAL_REQUIRED"
    )
    reversible: Mapped[Optional[bool]] = mapped_column(Boolean)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class MetricDefinition(Base, TimestampMixin):
    __tablename__ = "intervention_metric_definition"
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_intervention_metric_version"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(String(100), nullable=False)
    grain: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    domain: Mapped[Optional[str]] = mapped_column(String(100))
    directionality: Mapped[Optional[str]] = mapped_column(String(50))
    aggregation: Mapped[Optional[str]] = mapped_column(String(50))
    supported_scopes_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    authoritative_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_asset.id")
    )
    currently_measurable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    derived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    freshness_expectation_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Intervention(Base, TimestampMixin):
    __tablename__ = "intervention"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        UniqueConstraint("identity_hash", name="uq_intervention_identity"),
        Index("ix_intervention_scope", "tenant_id", "site_id", "status"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    primary_opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.opportunity.id"), nullable=False
    )
    analytical_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.analytical_entity.id"), nullable=False
    )
    intervention_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.intervention_type_definition.id"), nullable=False
    )
    market_definition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.market_definition.id")
    )
    market_definition_version: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[InterventionStatus] = mapped_column(
        enum_type(InterventionStatus, "intervention_status"), nullable=False
    )
    feasibility: Mapped[FeasibilityState] = mapped_column(
        enum_type(FeasibilityState, "feasibility_state"), nullable=False
    )
    measurement_readiness: Mapped[MeasurementReadiness] = mapped_column(
        enum_type(MeasurementReadiness, "measurement_readiness"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    constraints_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    risk_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    effort: Mapped[Optional[str]] = mapped_column(String(10))
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4))
    actual_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4))
    proposed_by: Mapped[Optional[str]] = mapped_column(String(255))
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class InterventionHypothesis(Base):
    __tablename__ = "intervention_hypothesis"
    __table_args__ = (
        UniqueConstraint("intervention_id", name="uq_intervention_hypothesis"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.intervention.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_metric_key: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_direction: Mapped[ExpectedDirection] = mapped_column(
        enum_type(ExpectedDirection, "expected_direction"), nullable=False
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.analytical_entity.id"), nullable=False
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    expected_magnitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MeasurementContract(Base, TimestampMixin):
    __tablename__ = "measurement_contract"
    __table_args__ = (
        UniqueConstraint("intervention_id", "version", name="uq_measurement_contract_version"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.intervention.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    baseline_strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    baseline_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    baseline_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    measurement_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    measurement_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    washout_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comparison_method: Mapped[str] = mapped_column(String(50), nullable=False)
    minimum_evidence: Mapped[DemandEvidenceStrength] = mapped_column(
        enum_type(DemandEvidenceStrength, "demand_evidence_strength"), nullable=False
    )
    freshness_days: Mapped[int] = mapped_column(Integer, nullable=False)
    exclusions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    method_version: Mapped[str] = mapped_column(String(50), nullable=False)


class MeasurementMetric(Base):
    __tablename__ = "measurement_metric"
    __table_args__ = (
        UniqueConstraint(
            "measurement_contract_id",
            "metric_definition_id",
            "role",
            name="uq_measurement_metric_role",
        ),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    measurement_contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.measurement_contract.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.intervention_metric_definition.id"),
        nullable=False,
    )
    role: Mapped[MetricRole] = mapped_column(enum_type(MetricRole, "metric_role"), nullable=False)
    expected_direction: Mapped[ExpectedDirection] = mapped_column(
        enum_type(ExpectedDirection, "expected_direction"), nullable=False
    )


class InterventionLifecycleEvent(Base):
    __tablename__ = "intervention_lifecycle_event"
    __table_args__ = (
        Index("ix_intervention_lifecycle_history", "intervention_id", "occurred_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.intervention.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[Optional[InterventionStatus]] = mapped_column(
        enum_type(InterventionStatus, "intervention_status")
    )
    to_status: Mapped[InterventionStatus] = mapped_column(
        enum_type(InterventionStatus, "intervention_status"), nullable=False
    )
    actor: Mapped[Optional[str]] = mapped_column(String(255))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InterventionExecution(Base):
    __tablename__ = "intervention_execution"
    __table_args__ = (
        Index("ix_intervention_execution_history", "intervention_id", "actual_started_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.intervention.id", ondelete="CASCADE"),
        nullable=False,
    )
    planned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    executor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    actual_parameters_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    artifact_reference: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class Experiment(Base, TimestampMixin):
    __tablename__ = "experiment"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        Index("ix_experiment_scope", "tenant_id", "site_id", "status"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.intervention.id"), nullable=False
    )
    measurement_contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.measurement_contract.id"), nullable=False
    )
    experiment_type: Mapped[ExperimentType] = mapped_column(
        enum_type(ExperimentType, "experiment_type"), nullable=False
    )
    status: Mapped[ExperimentStatus] = mapped_column(
        enum_type(ExperimentStatus, "experiment_status"), nullable=False
    )
    method_version: Mapped[str] = mapped_column(String(50), nullable=False)
    invalidation_reason: Mapped[Optional[str]] = mapped_column(String(100))
    planned_sample_size: Mapped[Optional[int]] = mapped_column(Integer)
    observed_sample_size: Mapped[Optional[int]] = mapped_column(Integer)
    contamination_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)


class InterventionOutcome(Base):
    __tablename__ = "intervention_outcome"
    __table_args__ = (
        UniqueConstraint("identity_hash", name="uq_intervention_outcome_identity"),
        Index("ix_intervention_outcome_history", "intervention_id", "evaluated_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.intervention.id", ondelete="CASCADE"),
        nullable=False,
    )
    measurement_contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.measurement_contract.id"), nullable=False
    )
    state: Mapped[OutcomeState] = mapped_column(
        enum_type(OutcomeState, "outcome_state"), nullable=False
    )
    expectation_result: Mapped[str] = mapped_column(String(50), nullable=False)
    baseline_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    post_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    absolute_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    relative_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    evidence_sufficiency: Mapped[DemandEvidenceStrength] = mapped_column(
        enum_type(DemandEvidenceStrength, "demand_evidence_strength"), nullable=False
    )
    completeness: Mapped[str] = mapped_column(String(50), nullable=False)
    causal_attribution: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    limitations_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    method_version: Mapped[str] = mapped_column(String(50), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StrategicObjective(Base, TimestampMixin):
    __tablename__ = "strategic_objective"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        Index("ix_strategic_objective_scope", "tenant_id", "site_id", "lifecycle"),
        Index("ix_strategic_objective_attention", "measurement_health", "decomposition_state"),
        CheckConstraint(
            "origin NOT IN ('STATISTICAL', 'AI_PROPOSED') OR lifecycle IN ('DRAFT', 'PROPOSED')",
            name="ck_objective_non_authoritative_origin",
        ),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    level: Mapped[ObjectiveLevel] = mapped_column(
        enum_type(ObjectiveLevel, "objective_level"), nullable=False
    )
    objective_type: Mapped[ObjectiveType] = mapped_column(
        enum_type(ObjectiveType, "objective_type"), nullable=False
    )
    lifecycle: Mapped[ObjectiveLifecycle] = mapped_column(
        enum_type(ObjectiveLifecycle, "objective_lifecycle"), nullable=False
    )
    origin: Mapped[ObjectiveOrigin] = mapped_column(
        enum_type(ObjectiveOrigin, "objective_origin"), nullable=False
    )
    approval_state: Mapped[ObjectiveApproval] = mapped_column(
        enum_type(ObjectiveApproval, "objective_approval"), nullable=False
    )
    progress_state: Mapped[ObjectiveProgress] = mapped_column(
        enum_type(ObjectiveProgress, "objective_progress"), nullable=False
    )
    measurement_health: Mapped[ObjectiveMeasurementHealth] = mapped_column(
        enum_type(ObjectiveMeasurementHealth, "objective_measurement_health"), nullable=False
    )
    decomposition_state: Mapped[DecompositionState] = mapped_column(
        enum_type(DecompositionState, "decomposition_state"), nullable=False
    )
    feasibility_state: Mapped[ObjectiveFeasibility] = mapped_column(
        enum_type(ObjectiveFeasibility, "objective_feasibility"), nullable=False
    )
    feasibility_reason: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    deadline: Mapped[Optional[date]] = mapped_column(Date)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False, default="SITE")
    scope_key: Mapped[Optional[str]] = mapped_column(Text)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    supersedes_objective_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.strategic_objective.id")
    )


class ObjectiveRelationship(Base):
    __tablename__ = "objective_relationship"
    __table_args__ = (
        UniqueConstraint(
            "source_objective_id",
            "target_objective_id",
            "relationship_type",
            name="uq_objective_relationship",
        ),
        CheckConstraint(
            "source_objective_id <> target_objective_id", name="ck_objective_no_self_edge"
        ),
        Index("ix_objective_relationship_source", "source_objective_id"),
        Index("ix_objective_relationship_target", "target_objective_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    source_objective_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.strategic_objective.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_objective_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.strategic_objective.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type: Mapped[ObjectiveRelationshipType] = mapped_column(
        enum_type(ObjectiveRelationshipType, "objective_relationship_type"), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ObjectiveTarget(Base, TimestampMixin):
    __tablename__ = "objective_target"
    __table_args__ = (
        Index("ix_objective_target_objective", "objective_id", "measurement_health"),
        CheckConstraint(
            "target_value IS NOT NULL OR condition_json <> '{}'::jsonb", name="ck_target_condition"
        ),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    objective_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.strategic_objective.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.intervention_metric_definition.id"),
        nullable=False,
    )
    family: Mapped[TargetFamily] = mapped_column(
        enum_type(TargetFamily, "target_family"), nullable=False
    )
    direction: Mapped[TargetDirection] = mapped_column(
        enum_type(TargetDirection, "target_direction"), nullable=False
    )
    unit: Mapped[str] = mapped_column(String(100), nullable=False)
    target_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    target_upper_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    condition_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    baseline_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    baseline_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    baseline_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    current_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    measurement_window: Mapped[Optional[str]] = mapped_column(String(100))
    aggregation: Mapped[Optional[str]] = mapped_column(String(50))
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    entity_scope_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    measurement_binding_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    measurement_health: Mapped[ObjectiveMeasurementHealth] = mapped_column(
        enum_type(ObjectiveMeasurementHealth, "objective_measurement_health"), nullable=False
    )
    approval_state: Mapped[ObjectiveApproval] = mapped_column(
        enum_type(ObjectiveApproval, "objective_approval"), nullable=False
    )
    origin: Mapped[ObjectiveOrigin] = mapped_column(
        enum_type(ObjectiveOrigin, "objective_origin"), nullable=False
    )
    suggested_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    override_rationale: Mapped[Optional[str]] = mapped_column(Text)


class ObjectiveMeasurement(Base):
    __tablename__ = "objective_measurement"
    __table_args__ = (
        UniqueConstraint("identity_hash", name="uq_objective_measurement_identity"),
        Index("ix_objective_measurement_target", "target_id", "measured_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.objective_target.id", ondelete="CASCADE"),
        nullable=False,
    )
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    unit: Mapped[str] = mapped_column(String(100), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_asset.id")
    )
    source_reference: Mapped[Optional[str]] = mapped_column(Text)
    rights_policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id")
    )
    freshness_state: Mapped[str] = mapped_column(String(50), nullable=False)
    readiness_state: Mapped[str] = mapped_column(String(50), nullable=False)
    method_key: Mapped[str] = mapped_column(String(100), nullable=False)
    method_version: Mapped[str] = mapped_column(String(50), nullable=False)
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class DecompositionPlan(Base, TimestampMixin):
    __tablename__ = "decomposition_plan"
    __table_args__ = (
        Index("ix_decomposition_plan_objective", "objective_id", "status"),
        Index(
            "uq_decomposition_plan_selected",
            "objective_id",
            unique=True,
            postgresql_where=text("selected"),
        ),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    objective_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.strategic_objective.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[DecompositionPlanStatus] = mapped_column(
        enum_type(DecompositionPlanStatus, "decomposition_plan_status"), nullable=False
    )
    origin: Mapped[ObjectiveOrigin] = mapped_column(
        enum_type(ObjectiveOrigin, "objective_origin"), nullable=False
    )
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class DecompositionRule(Base, TimestampMixin):
    __tablename__ = "decomposition_rule"
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_decomposition_rule_version"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    parent_level: Mapped[ObjectiveLevel] = mapped_column(
        enum_type(ObjectiveLevel, "objective_level"), nullable=False
    )
    parent_type: Mapped[ObjectiveType] = mapped_column(
        enum_type(ObjectiveType, "objective_type"), nullable=False
    )
    output_level: Mapped[ObjectiveLevel] = mapped_column(
        enum_type(ObjectiveLevel, "objective_level"), nullable=False
    )
    output_type: Mapped[ObjectiveType] = mapped_column(
        enum_type(ObjectiveType, "objective_type"), nullable=False
    )
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    required_metrics_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    supported_units_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    output_metric_key: Mapped[str] = mapped_column(String(100), nullable=False)
    assumptions_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    readiness_policy_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rights_requirements_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ObjectiveDerivation(Base):
    __tablename__ = "objective_derivation"
    __table_args__ = (
        UniqueConstraint("identity_hash", name="uq_objective_derivation_identity"),
        Index("ix_objective_derivation_parent", "source_objective_id", "executed_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    decomposition_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.decomposition_plan.id"), nullable=False
    )
    source_objective_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.strategic_objective.id"), nullable=False
    )
    generated_objective_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.strategic_objective.id")
    )
    generated_target_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.objective_target.id")
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.decomposition_rule.id"), nullable=False
    )
    rule_key: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(50), nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    required_inputs_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    input_values_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    source_references_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    assumptions_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    rights_state: Mapped[str] = mapped_column(String(50), nullable=False)
    readiness_state: Mapped[str] = mapped_column(String(50), nullable=False)
    result_status: Mapped[DerivationResultStatus] = mapped_column(
        enum_type(DerivationResultStatus, "derivation_result_status"), nullable=False
    )
    blocked_reason: Mapped[Optional[str]] = mapped_column(Text)
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes_derivation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.objective_derivation.id")
    )
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ObjectiveAuditEvent(Base):
    __tablename__ = "objective_audit_event"
    __table_args__ = (
        Index("ix_objective_audit_history", "objective_id", "occurred_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    objective_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.strategic_objective.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    before_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    after_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RecommendationPolicy(Base, TimestampMixin):
    __tablename__ = "recommendation_policy"
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_recommendation_policy_version"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    provider_key: Mapped[str] = mapped_column(String(100), nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    policy_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationRun(Base):
    __tablename__ = "recommendation_run"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        UniqueConstraint("context_hash", name="uq_recommendation_run_context"),
        Index("ix_recommendation_run_scope", "tenant_id", "site_id", "started_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.opportunity.id"), nullable=False
    )
    recommendation_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.recommendation_policy.id"), nullable=False
    )
    status: Mapped[RecommendationRunStatus] = mapped_column(
        enum_type(RecommendationRunStatus, "recommendation_run_status"), nullable=False
    )
    provider_key: Mapped[str] = mapped_column(String(100), nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    model_configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    provider_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    validation_errors_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    repair_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Recommendation(Base, TimestampMixin):
    __tablename__ = "recommendation"
    __table_args__ = (
        UniqueConstraint("identity_hash", name="uq_recommendation_identity"),
        Index("ix_recommendation_scope", "tenant_id", "site_id", "status"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.recommendation_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.opportunity.id"), nullable=False
    )
    analytical_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.analytical_entity.id"), nullable=False
    )
    market_definition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.market_definition.id")
    )
    market_definition_version: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[RecommendationStatus] = mapped_column(
        enum_type(RecommendationStatus, "recommendation_status"), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    assumptions_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    limitations_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class RecommendationCandidate(Base, TimestampMixin):
    __tablename__ = "recommendation_candidate"
    __table_args__ = (
        UniqueConstraint("recommendation_id", "rank", name="uq_recommendation_candidate_rank"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.recommendation.id", ondelete="CASCADE"),
        nullable=False,
    )
    intervention_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.intervention_type_definition.id"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    fit: Mapped[str] = mapped_column(String(50), nullable=False)
    validation_state: Mapped[CandidateValidationState] = mapped_column(
        enum_type(CandidateValidationState, "candidate_validation_state"), nullable=False
    )
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    target_metric_key: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_direction: Mapped[ExpectedDirection] = mapped_column(
        enum_type(ExpectedDirection, "expected_direction"), nullable=False
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    assumptions_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    limitations_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    feasibility: Mapped[FeasibilityState] = mapped_column(
        enum_type(FeasibilityState, "feasibility_state"), nullable=False
    )
    measurement_readiness: Mapped[MeasurementReadiness] = mapped_column(
        enum_type(MeasurementReadiness, "measurement_readiness"), nullable=False
    )
    validation_errors_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    accepted_intervention_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.intervention.id")
    )


class RecommendationEvidence(Base):
    __tablename__ = "recommendation_evidence"
    __table_args__ = (
        UniqueConstraint(
            "recommendation_id", "evidence_package_id", name="uq_recommendation_evidence"
        ),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.recommendation.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.evidence_package.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RecommendationReview(Base):
    __tablename__ = "recommendation_review"
    __table_args__ = (
        Index("ix_recommendation_review_history", "recommendation_id", "reviewed_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.recommendation.id", ondelete="CASCADE"),
        nullable=False,
    )
    decision: Mapped[RecommendationReviewDecision] = mapped_column(
        enum_type(RecommendationReviewDecision, "recommendation_review_decision"), nullable=False
    )
    reviewer: Mapped[str] = mapped_column(String(255), nullable=False)
    reason_category: Mapped[Optional[str]] = mapped_column(String(100))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    accepted_candidate_ids_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CompetitiveEventPolicy(Base, TimestampMixin):
    __tablename__ = "competitive_event_policy"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "site_id",
            "name",
            "policy_version",
            name="uq_competitive_event_policy_version",
        ),
        Index("ix_competitive_event_policy_scope", "tenant_id", "site_id", "active"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.site.id")
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    thresholds_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class CompetitiveEvent(Base):
    __tablename__ = "competitive_event"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_competitive_event_confidence"),
        CheckConstraint("provider_cost = 0", name="ck_competitive_event_zero_provider_cost"),
        UniqueConstraint(
            "tenant_id", "site_id", "identity_hash", name="uq_competitive_event_identity"
        ),
        UniqueConstraint("tenant_id", "site_id", "id", name="uq_competitive_event_scope_id"),
        Index("ix_competitive_event_timeline", "tenant_id", "site_id", "event_time"),
        Index("ix_competitive_event_type", "tenant_id", "site_id", "event_domain", "event_type"),
        Index("ix_competitive_event_subject", "tenant_id", "site_id", "subject_key"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    public_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.organization.id")
    )
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_type: Mapped[CompetitiveSubjectType] = mapped_column(
        enum_type(CompetitiveSubjectType, "competitive_subject_type"), nullable=False
    )
    subject_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    subject_key: Mapped[str] = mapped_column(Text, nullable=False)
    subject_domain: Mapped[Optional[str]] = mapped_column(String(253))
    subject_url: Mapped[Optional[str]] = mapped_column(Text)
    event_domain: Mapped[CompetitiveEventDomain] = mapped_column(
        enum_type(CompetitiveEventDomain, "competitive_event_domain"), nullable=False
    )
    event_type: Mapped[CompetitiveEventType] = mapped_column(
        enum_type(CompetitiveEventType, "competitive_event_type"), nullable=False
    )
    event_subtype: Mapped[Optional[str]] = mapped_column(String(100))
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    effective_end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    semantic_class: Mapped[EventSemanticClass] = mapped_column(
        enum_type(EventSemanticClass, "event_semantic_class"), nullable=False
    )
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    magnitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    magnitude_unit: Mapped[Optional[str]] = mapped_column(String(32))
    status: Mapped[CompetitiveEventStatus] = mapped_column(
        enum_type(CompetitiveEventStatus, "competitive_event_status"),
        nullable=False,
        default=CompetitiveEventStatus.ACTIVE,
    )
    synthesis_method: Mapped[str] = mapped_column(String(100), nullable=False)
    synthesis_method_version: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.competitive_event_policy.id"), nullable=False
    )
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    rights_policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id")
    )
    rights_policy_version: Mapped[Optional[str]] = mapped_column(String(100))
    effective_rights_status: Mapped[RightsStatus] = mapped_column(
        enum_type(RightsStatus, "rights_status"), nullable=False
    )
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    correction_reason: Mapped[Optional[str]] = mapped_column(Text)
    replaced_by_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.competitive_event.id")
    )
    provider_cost: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=Decimal("0")
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CompetitiveEventEvidence(Base):
    __tablename__ = "competitive_event_evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "competitive_event_id"],
            [
                f"{SCHEMA}.competitive_event.tenant_id",
                f"{SCHEMA}.competitive_event.site_id",
                f"{SCHEMA}.competitive_event.id",
            ],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "competitive_event_id",
            "source_asset",
            "source_record_id",
            "evidence_role",
            name="uq_competitive_event_evidence",
        ),
        Index("ix_competitive_event_evidence_source", "source_asset", "source_record_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    competitive_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_asset: Mapped[str] = mapped_column(String(150), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    observation_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_role: Mapped[EvidenceRole] = mapped_column(
        enum_type(EvidenceRole, "competitive_evidence_role"), nullable=False
    )
    semantic_class: Mapped[EventSemanticClass] = mapped_column(
        enum_type(EventSemanticClass, "event_semantic_class"), nullable=False
    )
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    data_source_connection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_source_connection.id")
    )
    ingestion_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.ingestion_run.id")
    )
    rights_policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id")
    )
    rights_policy_version: Mapped[Optional[str]] = mapped_column(String(100))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CompetitiveEventRelationship(Base):
    __tablename__ = "competitive_event_relationship"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "from_event_id"],
            [
                f"{SCHEMA}.competitive_event.tenant_id",
                f"{SCHEMA}.competitive_event.site_id",
                f"{SCHEMA}.competitive_event.id",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "to_event_id"],
            [
                f"{SCHEMA}.competitive_event.tenant_id",
                f"{SCHEMA}.competitive_event.site_id",
                f"{SCHEMA}.competitive_event.id",
            ],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "from_event_id <> to_event_id", name="ck_competitive_event_relationship_not_self"
        ),
        UniqueConstraint(
            "from_event_id",
            "to_event_id",
            "relationship_type",
            name="uq_competitive_event_relationship",
        ),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    from_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    to_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    relationship_type: Mapped[EventRelationshipType] = mapped_column(
        enum_type(EventRelationshipType, "competitive_event_relationship_type"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PipelineDefinition(Base, TimestampMixin):
    __tablename__ = "pipeline_definition"
    __table_args__ = (
        UniqueConstraint("key", name="uq_pipeline_definition_key"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    handler_key: Mapped[str] = mapped_column(String(100), nullable=False)
    data_source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_source.id")
    )
    paid_provider: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=Decimal("0")
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class PipelineDependency(Base):
    __tablename__ = "pipeline_dependency"
    __table_args__ = (
        Index(
            "uq_pipeline_dependency_scope",
            "tenant_id",
            "site_id",
            "upstream_pipeline_id",
            "downstream_pipeline_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(
            "upstream_pipeline_id <> downstream_pipeline_id", name="ck_pipeline_dependency_self"
        ),
        Index(
            "ix_pipeline_dependency_downstream", "tenant_id", "site_id", "downstream_pipeline_id"
        ),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    upstream_pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.pipeline_definition.id"), nullable=False
    )
    downstream_pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.pipeline_definition.id"), nullable=False
    )
    policy: Mapped[DependencyPolicy] = mapped_column(
        enum_type(DependencyPolicy, "dependency_policy"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ScheduleDefinition(Base, TimestampMixin):
    __tablename__ = "schedule_definition"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        UniqueConstraint("tenant_id", "name", name="uq_schedule_definition_tenant_name"),
        CheckConstraint("max_attempts >= 1", name="ck_schedule_max_attempts"),
        CheckConstraint("retry_delay_seconds >= 0", name="ck_schedule_retry_delay"),
        CheckConstraint(
            "freshness_sla_seconds IS NULL OR freshness_sla_seconds > 0",
            name="ck_schedule_freshness_sla",
        ),
        Index("ix_schedule_due", "status", "next_scheduled_at"),
        Index("ix_schedule_tenant_site", "tenant_id", "site_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.organization.id")
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.pipeline_definition.id"), nullable=False
    )
    data_source_connection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_source_connection.id")
    )
    rights_policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="UTC")
    status: Mapped[ScheduleStatus] = mapped_column(
        enum_type(ScheduleStatus, "schedule_status"),
        nullable=False,
        default=ScheduleStatus.DISABLED,
    )
    next_scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    exponential_backoff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    freshness_sla_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    automatic_catchup_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=172800)
    terminal_horizon_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=604800)
    retry_profile: Mapped[str] = mapped_column(
        String(50), nullable=False, default="LOCAL_DETERMINISTIC"
    )
    reconciliation_window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1")
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class ScheduledTarget(Base, TimestampMixin):
    __tablename__ = "scheduled_target"
    __table_args__ = (
        UniqueConstraint("schedule_id", "target_type", "target_key", name="uq_scheduled_target"),
        Index("ix_scheduled_target_tenant", "tenant_id", "site_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.schedule_definition.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_key: Mapped[str] = mapped_column(Text, nullable=False)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class OrchestrationObligation(Base):
    __tablename__ = "orchestration_obligation"
    __table_args__ = (
        Index(
            "uq_obligation_identity",
            "schedule_id",
            "target_id",
            "window_start",
            "window_end",
            "policy_version",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_obligation_queue", "status", "next_attempt_at", "due_at"),
        Index("ix_obligation_scope", "tenant_id", "site_id", "pipeline_id", "due_at"),
        CheckConstraint("window_end > window_start", name="ck_obligation_window"),
        CheckConstraint("attempt_count >= 0", name="ck_obligation_attempt_count"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.pipeline_definition.id"), nullable=False
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.schedule_definition.id"), nullable=False
    )
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.scheduled_target.id")
    )
    data_source_connection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_source_connection.id")
    )
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ObligationStatus] = mapped_column(
        enum_type(ObligationStatus, "obligation_status"), nullable=False
    )
    completion_outcome: Mapped[Optional[CompletionOutcome]] = mapped_column(
        enum_type(CompletionOutcome, "completion_outcome")
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    satisfied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ingestion_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.ingestion_run.id")
    )
    failure_category: Mapped[Optional[FailureCategory]] = mapped_column(
        enum_type(FailureCategory, "failure_category")
    )
    status_reason: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ExecutorHeartbeat(Base):
    __tablename__ = "executor_heartbeat"
    __table_args__ = (
        UniqueConstraint("executor_id", "role", name="uq_executor_heartbeat_identity"),
        Index("ix_executor_heartbeat_liveness", "role", "last_heartbeat_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    executor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[ExecutorRole] = mapped_column(
        enum_type(ExecutorRole, "executor_role"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class OrchestrationRun(Base):
    __tablename__ = "orchestration_run"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        Index(
            "uq_orchestration_schedule_occurrence",
            "schedule_id",
            "scheduled_for",
            "target_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
            postgresql_where=text("schedule_id IS NOT NULL"),
        ),
        CheckConstraint("estimated_provider_cost >= 0", name="ck_orchestration_estimated_cost"),
        CheckConstraint(
            "actual_provider_cost IS NULL OR actual_provider_cost >= 0",
            name="ck_orchestration_actual_cost",
        ),
        CheckConstraint(
            "backfill_end IS NULL OR backfill_start IS NOT NULL",
            name="ck_orchestration_backfill_pair",
        ),
        CheckConstraint(
            "backfill_end IS NULL OR backfill_end >= backfill_start",
            name="ck_orchestration_backfill_bounds",
        ),
        Index("ix_orchestration_queue", "status", "available_at", "requested_at"),
        Index("ix_orchestration_history", "tenant_id", "site_id", "pipeline_id", "requested_at"),
        Index("ix_orchestration_run_obligation", "obligation_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.organization.id")
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.pipeline_definition.id"), nullable=False
    )
    schedule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.schedule_definition.id")
    )
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.scheduled_target.id")
    )
    data_source_connection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_source_connection.id")
    )
    rights_policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_rights_policy.id")
    )
    upstream_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.orchestration_run.id")
    )
    ingestion_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.ingestion_run.id")
    )
    obligation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.orchestration_obligation.id")
    )
    trigger_type: Mapped[TriggerType] = mapped_column(
        enum_type(TriggerType, "trigger_type"), nullable=False
    )
    status: Mapped[OrchestrationStatus] = mapped_column(
        enum_type(OrchestrationStatus, "orchestration_status"), nullable=False
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    backfill_start: Mapped[Optional[date]] = mapped_column(Date)
    backfill_end: Mapped[Optional[date]] = mapped_column(Date)
    estimated_provider_cost: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=Decimal("0")
    )
    actual_provider_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    error_classification: Mapped[Optional[str]] = mapped_column(String(100))
    error_detail: Mapped[Optional[str]] = mapped_column(Text)
    completion_outcome: Mapped[Optional[CompletionOutcome]] = mapped_column(
        enum_type(CompletionOutcome, "completion_outcome")
    )
    readiness_state: Mapped[ReadinessState] = mapped_column(
        enum_type(ReadinessState, "readiness_state"),
        nullable=False,
        default=ReadinessState.READY,
    )
    readiness_detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ExecutionAttempt(Base):
    __tablename__ = "execution_attempt"
    __table_args__ = (
        UniqueConstraint(
            "orchestration_run_id", "attempt_number", name="uq_execution_attempt_number"
        ),
        Index("ix_execution_attempt_status", "status", "started_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orchestration_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.orchestration_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    trigger_type: Mapped[TriggerType] = mapped_column(
        enum_type(TriggerType, "trigger_type"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[OrchestrationStatus] = mapped_column(
        enum_type(OrchestrationStatus, "orchestration_status"), nullable=False
    )
    worker_id: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ingestion_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.ingestion_run.id")
    )
    error_classification: Mapped[Optional[str]] = mapped_column(String(100))
    error_detail: Mapped[Optional[str]] = mapped_column(Text)
    failure_category: Mapped[Optional[FailureCategory]] = mapped_column(
        enum_type(FailureCategory, "failure_category")
    )
    retry_after_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    estimated_provider_cost: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=Decimal("0")
    )
    actual_provider_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FreshnessState(Base):
    __tablename__ = "freshness_state"
    __table_args__ = (
        Index(
            "uq_freshness_scope",
            "tenant_id",
            "site_id",
            "pipeline_id",
            "schedule_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_freshness_stale", "tenant_id", "stale_since"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.pipeline_definition.id"), nullable=False
    )
    schedule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.schedule_definition.id")
    )
    last_attempted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_successful_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expected_next_execution_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    freshness_sla_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    stale_since: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CostBudget(Base, TimestampMixin):
    __tablename__ = "cost_budget"
    __table_args__ = (
        Index(
            "uq_cost_budget_scope",
            "tenant_id",
            "site_id",
            "data_source_id",
            "pipeline_id",
            "schedule_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("daily_limit IS NULL OR daily_limit >= 0", name="ck_budget_daily"),
        CheckConstraint("monthly_limit IS NULL OR monthly_limit >= 0", name="ck_budget_monthly"),
        CheckConstraint("per_run_limit IS NULL OR per_run_limit >= 0", name="ck_budget_per_run"),
        Index("ix_cost_budget_tenant", "tenant_id", "active"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    data_source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_source.id")
    )
    pipeline_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.pipeline_definition.id")
    )
    schedule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.schedule_definition.id")
    )
    daily_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    monthly_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    per_run_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CostLedgerEntry(Base):
    __tablename__ = "cost_ledger_entry"
    __table_args__ = (
        UniqueConstraint("orchestration_run_id", name="uq_cost_ledger_run"),
        Index("ix_cost_ledger_scope_date", "tenant_id", "occurred_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    data_source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.data_source.id")
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.pipeline_definition.id"), nullable=False
    )
    schedule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.schedule_definition.id")
    )
    orchestration_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.orchestration_run.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OperationalAlert(Base):
    __tablename__ = "operational_alert"
    __table_args__ = (
        Index(
            "uq_operational_alert_open",
            "tenant_id",
            "deduplication_key",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
        ),
        Index("ix_operational_alert_tenant_status", "tenant_id", "status", "opened_at"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenant.id"), nullable=False
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    pipeline_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.pipeline_definition.id")
    )
    schedule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.schedule_definition.id")
    )
    orchestration_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.orchestration_run.id")
    )
    alert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        enum_type(AlertStatus, "alert_status"), nullable=False, default=AlertStatus.OPEN
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
