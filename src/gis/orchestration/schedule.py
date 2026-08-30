from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ScheduleExpressionError(ValueError):
    pass


def _matches(value: int, expression: str, minimum: int, maximum: int) -> bool:
    for token in expression.split(","):
        token = token.strip()
        if token == "*":
            return True
        if token.startswith("*/"):
            try:
                step = int(token[2:])
            except ValueError as error:
                raise ScheduleExpressionError("invalid cron step") from error
            if step < 1:
                raise ScheduleExpressionError("cron step must be positive")
            if (value - minimum) % step == 0:
                return True
            continue
        try:
            expected = int(token)
        except ValueError as error:
            raise ScheduleExpressionError(f"unsupported cron token: {token}") from error
        if not minimum <= expected <= maximum:
            raise ScheduleExpressionError(f"cron value {expected} outside {minimum}-{maximum}")
        if value == expected:
            return True
    return False


def validate_cron(expression: str) -> None:
    fields = expression.split()
    if len(fields) != 5:
        raise ScheduleExpressionError("cron expression must contain five fields")
    for field, limits in zip(fields, ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))):
        _matches(limits[0], field, *limits)


def next_occurrence(expression: str, timezone_name: str, after: datetime) -> datetime:
    """Return the next UTC occurrence; ambiguous fall-back times run only on fold zero."""
    if after.tzinfo is None:
        raise ScheduleExpressionError("after must be timezone-aware")
    validate_cron(expression)
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ScheduleExpressionError(f"unknown timezone: {timezone_name}") from error
    minute, hour, month_day, month, week_day = expression.split()
    candidate = after.astimezone(timezone.utc).replace(second=0, microsecond=0) + timedelta(
        minutes=1
    )
    deadline = candidate + timedelta(days=366 * 2)
    while candidate <= deadline:
        local = candidate.astimezone(zone)
        cron_week_day = (local.weekday() + 1) % 7
        if (
            local.fold == 0
            and _matches(local.minute, minute, 0, 59)
            and _matches(local.hour, hour, 0, 23)
            and _matches(local.day, month_day, 1, 31)
            and _matches(local.month, month, 1, 12)
            and _matches(cron_week_day, week_day, 0, 6)
        ):
            return candidate
        candidate += timedelta(minutes=1)
    raise ScheduleExpressionError("no occurrence found within two years")
