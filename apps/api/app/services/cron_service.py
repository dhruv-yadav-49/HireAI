import zoneinfo
from datetime import datetime
from croniter import croniter


class CronService:
    """Helper service for calculating and validating cron schedule intervals."""

    @staticmethod
    def get_next_run(
        cron_expression: str, base_time: datetime, timezone_str: str = "UTC"
    ) -> datetime:
        """Calculates the next execution datetime in UTC based on organization's timezone settings."""
        # Ensure timezone defaults if none is provided
        tz_name = timezone_str or "UTC"
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")

        # Convert UTC base time to target local timezone
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        base_local = base_time.astimezone(tz)

        # Remove microseconds from base_local as croniter works up to minute granularity
        base_local = base_local.replace(second=0, microsecond=0)

        # Get next execution tick from croniter
        iter_cron = croniter(cron_expression, base_local)
        next_local = iter_cron.get_next(datetime)

        # Convert back to UTC and return
        return next_local.astimezone(zoneinfo.ZoneInfo("UTC"))

    @staticmethod
    def is_valid_cron(cron_expression: str) -> bool:
        """Checks if a string represents a valid crontab syntax expression."""
        return croniter.is_valid(cron_expression)
