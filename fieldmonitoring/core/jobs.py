"""Scheduled jobs. `manage.py run_jobs` calls `run_due_jobs` every few minutes (cron or the
scheduler container); each job decides in programme time whether it is due, so daylight-saving
shifts and server timezones cannot move it.
"""

from datetime import datetime, timedelta

from django.db import IntegrityError, transaction

from . import clock
from .models import JobRun, ProgrammeConfig


def _claim(job: str, key: str) -> bool:
    try:
        with transaction.atomic():
            JobRun.objects.create(job=job, run_key=key)
        return True
    except IntegrityError:
        return False


def auto_close_if_due(now: datetime | None = None) -> int | None:
    """BR-8 at the configured time (20:00 programme time)."""
    from fieldmonitoring.visits.services import auto_close

    config = ProgrammeConfig.get()
    now = now or clock.now()
    local = now.astimezone(config.tz)
    if local.time() < config.auto_close_time:
        return None
    if not _claim("auto_close", local.date().isoformat()):
        return None
    cutoff = clock.at_local(local.date(), config.auto_close_time, config) - timedelta(
        minutes=config.auto_close_grace_minutes
    )
    return auto_close(cutoff)


def warning_if_due(now: datetime | None = None):
    """BR-14 on the configured weekday and time (Monday 06:00 programme time)."""
    from fieldmonitoring.warning.services import generate

    config = ProgrammeConfig.get()
    now = now or clock.now()
    local = now.astimezone(config.tz)
    if local.weekday() != config.warning_weekday or local.time() < config.warning_time:
        return None
    if not _claim("weekly_warning", local.date().isoformat()):
        return None
    return generate(local.date())


def run_due_jobs(now: datetime | None = None) -> dict:
    return {"auto_close": auto_close_if_due(now), "warning": warning_if_due(now)}
