"""Programme-time helpers. All business-day arithmetic goes through here."""

from datetime import UTC, date, datetime, time, timedelta

from django.utils import timezone

from .models import ProgrammeConfig


def now() -> datetime:
    """Server time in UTC. Never the device clock (CLAUDE.md non-negotiable 2)."""
    return timezone.now()


def local_date(dt: datetime, config: ProgrammeConfig | None = None) -> date:
    config = config or ProgrammeConfig.get()
    return dt.astimezone(config.tz).date()


def today(config: ProgrammeConfig | None = None) -> date:
    return local_date(now(), config)


def at_local(day: date, t: time, config: ProgrammeConfig | None = None) -> datetime:
    """The UTC instant of wall-clock time `t` on `day` in programme time."""
    config = config or ProgrammeConfig.get()
    return datetime.combine(day, t, tzinfo=config.tz).astimezone(UTC)


def local_day_bounds(day: date, config: ProgrammeConfig | None = None) -> tuple[datetime, datetime]:
    start = at_local(day, time.min, config)
    return start, at_local(day + timedelta(days=1), time.min, config)
