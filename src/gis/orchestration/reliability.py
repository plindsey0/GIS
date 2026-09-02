from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from gis.models import CompletionOutcome, FailureCategory, PipelineDefinition, ScheduleDefinition


@dataclass(frozen=True)
class RetryProfile:
    name: str
    delays: tuple[int, ...]
    retryable: frozenset[FailureCategory]
    reconciliation_delay_seconds: int | None = None


RETRY_PROFILES = {
    "DAILY_FREE_API": RetryProfile(
        "DAILY_FREE_API",
        (300, 900, 1800, *([3600] * 10)),
        frozenset(
            {
                FailureCategory.TRANSIENT_NETWORK,
                FailureCategory.PROVIDER_429,
                FailureCategory.PROVIDER_5XX,
                FailureCategory.UNKNOWN_RETRYABLE,
            }
        ),
        21600,
    ),
    "WEEKLY_FREE_API": RetryProfile(
        "WEEKLY_FREE_API",
        (900, 3600, 14400, 86400, 86400, 86400),
        frozenset(
            {
                FailureCategory.TRANSIENT_NETWORK,
                FailureCategory.PROVIDER_429,
                FailureCategory.PROVIDER_5XX,
                FailureCategory.UNKNOWN_RETRYABLE,
            }
        ),
        86400,
    ),
    "PAID_BOUNDED": RetryProfile(
        "PAID_BOUNDED",
        (900,),
        frozenset(
            {
                FailureCategory.TRANSIENT_NETWORK,
                FailureCategory.PROVIDER_429,
                FailureCategory.PROVIDER_5XX,
            }
        ),
    ),
    "LOCAL_DETERMINISTIC": RetryProfile(
        "LOCAL_DETERMINISTIC",
        (10, 30, 60, 300, 900),
        frozenset(
            {
                FailureCategory.TRANSIENT_NETWORK,
                FailureCategory.INTERNAL_PROCESSING_ERROR,
                FailureCategory.UNKNOWN_RETRYABLE,
            }
        ),
    ),
}


class ClassifiedFailure(RuntimeError):
    def __init__(
        self,
        category: FailureCategory,
        message: str,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.retry_after_seconds = retry_after_seconds


class CompletionPending(RuntimeError):
    def __init__(self, message: str, *, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def retry_profile(
    schedule: ScheduleDefinition | None, pipeline: PipelineDefinition
) -> RetryProfile:
    configured = schedule.retry_profile if schedule else None
    if configured in RETRY_PROFILES:
        profile = RETRY_PROFILES[configured]
    elif pipeline.paid_provider:
        profile = RETRY_PROFILES["PAID_BOUNDED"]
    else:
        profile = RETRY_PROFILES["LOCAL_DETERMINISTIC"]
    # Paid execution can never inherit an expansive retry profile accidentally.
    return RETRY_PROFILES["PAID_BOUNDED"] if pipeline.paid_provider else profile


def classify_failure(error: Exception) -> tuple[FailureCategory, int | None]:
    if isinstance(error, ClassifiedFailure):
        return error.category, error.retry_after_seconds
    if isinstance(error, (TimeoutError, ConnectionError)):
        return FailureCategory.TRANSIENT_NETWORK, None
    if isinstance(error, FileNotFoundError):
        return FailureCategory.CONFIGURATION_ERROR, None
    if isinstance(error, (ValueError, KeyError)):
        return FailureCategory.CONFIGURATION_ERROR, None
    return FailureCategory.INTERNAL_PROCESSING_ERROR, None


def collector_failure(message: str) -> ClassifiedFailure:
    normalized = message.casefold()
    if "429" in normalized or "rate limit" in normalized:
        category = FailureCategory.PROVIDER_429
    elif "401" in normalized or "authentication" in normalized or "credential" in normalized:
        category = FailureCategory.AUTHENTICATION_FAILED
    elif "403" in normalized or "authorization" in normalized or "permission" in normalized:
        category = FailureCategory.AUTHORIZATION_FAILED
    elif any(token in normalized for token in ("500", "502", "503", "504")):
        category = FailureCategory.PROVIDER_5XX
    elif "rights" in normalized:
        category = FailureCategory.RIGHTS_BLOCKED
    elif "budget" in normalized:
        category = FailureCategory.BUDGET_BLOCKED
    else:
        category = FailureCategory.UNKNOWN_RETRYABLE
    return ClassifiedFailure(category, message)


def completion_outcome(metadata: dict[str, object] | None) -> CompletionOutcome:
    value = (metadata or {}).get("completion_outcome", "SUCCEEDED_COMPLETE")
    return CompletionOutcome(str(value))


def retry_at(
    profile: RetryProfile,
    category: FailureCategory,
    attempt_number: int,
    now: datetime,
    provider_retry_after_seconds: int | None = None,
) -> datetime | None:
    if category not in profile.retryable or attempt_number > len(profile.delays):
        return None
    delay = profile.delays[attempt_number - 1]
    if provider_retry_after_seconds is not None:
        delay = max(delay, provider_retry_after_seconds)
    return now + timedelta(seconds=delay)
