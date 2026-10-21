"""Gathers data from the database and feeds it to the pure rules in `rules.py`."""

import statistics
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from django.db.models import Q

from authorization.models import Role, User
from fieldmonitoring.core import clock
from fieldmonitoring.core.models import ProgrammeConfig
from fieldmonitoring.registry.models import Worksite, WorksiteAssignment, WorksiteStatus
from fieldmonitoring.visits.models import Visit, VisitState

from . import rules
from .models import Pause, RoleThreshold


def pause_ranges(user: User) -> list[rules.DateRange]:
    ranges = []
    for pause in user.pauses.all():
        end = pause.ends_on
        if pause.cancelled_at:
            end = min(end, clock.local_date(pause.cancelled_at))
        if end > pause.starts_on:
            ranges.append((pause.starts_on, end))
    return ranges


def current_pause(user: User, day: date) -> Pause | None:
    for pause in user.pauses.filter(starts_on__lte=day, ends_on__gt=day, cancelled_at__isnull=True):
        return pause
    return None


def verified_days(user: User, until: date, config: ProgrammeConfig) -> set[date]:
    """BR-1 field days up to and including `until`."""
    _, end = clock.local_day_bounds(until, config)
    visits = Visit.objects.filter(user=user, state=VisitState.VERIFIED, checked_in_at__lt=end)
    return rules.field_days(visits.values_list("state", "checked_in_at"), config.tz)


def verified_count(user: User, start: date, end: date, config: ProgrammeConfig) -> int:
    lo, _ = clock.local_day_bounds(start, config)
    _, hi = clock.local_day_bounds(end, config)
    return Visit.objects.filter(
        user=user, state=VisitState.VERIFIED, checked_in_at__gte=lo, checked_in_at__lt=hi
    ).count()


@dataclass
class Presence:
    days_since: int
    last_verified_on: date | None
    threshold_days: int | None
    flagged: bool
    paused: bool
    paused_until: date | None
    verified_last_4_weeks: int


def presence(user: User, today: date, config=None, thresholds=None) -> Presence:
    """BR-2 and BR-3 for one user, as of `today`."""
    config = config or ProgrammeConfig.get()
    thresholds = thresholds or RoleThreshold.as_dict()
    days = verified_days(user, today, config)
    last = max(days, default=None)
    pauses = pause_ranges(user)
    days_since = rules.days_since_last_verified(last, user.onboarded_on, today, pauses)
    paused = rules.is_paused_on(today, pauses)
    pause = current_pause(user, today) if paused else None
    return Presence(
        days_since=days_since,
        last_verified_on=last,
        threshold_days=thresholds.get(user.role),
        flagged=rules.regularity_flagged(user.role, days_since, paused, thresholds),
        paused=paused,
        paused_until=pause.ends_on if pause else None,
        verified_last_4_weeks=verified_count(user, today - timedelta(days=27), today, config),
    )


def assigned_worksite_ids(user: User, on: date) -> set:
    """Assignments in force on `on` (Story 1.4: history stays computable)."""
    return set(
        WorksiteAssignment.objects.filter(user=user, assigned_on__lte=on, worksite__status=WorksiteStatus.ACTIVE)
        .filter(Q(unassigned_on__isnull=True) | Q(unassigned_on__gt=on))
        .values_list("worksite_id", flat=True)
    )


def coverage(user: User, start: date, end: date, config: ProgrammeConfig) -> tuple[int, int]:
    """(assigned worksites visited with a verified visit in the period, assigned at period end)."""
    assigned = assigned_worksite_ids(user, end)
    lo, _ = clock.local_day_bounds(start, config)
    _, hi = clock.local_day_bounds(end, config)
    visited = set(
        Visit.objects.filter(
            user=user,
            state=VisitState.VERIFIED,
            worksite_id__in=assigned,
            checked_in_at__gte=lo,
            checked_in_at__lt=hi,
        ).values_list("worksite_id", flat=True)
    )
    return len(visited), len(assigned)


def team_row(user: User, today: date, config, thresholds) -> dict:
    p = presence(user, today, config, thresholds)
    start = today - timedelta(days=27)
    visited, assigned = coverage(user, start, today, config)
    lo, _ = clock.local_day_bounds(start, config)
    durations = list(
        Visit.objects.filter(
            user=user, state=VisitState.VERIFIED, checked_in_at__gte=lo, time_on_site_s__isnull=False
        ).values_list("time_on_site_s", flat=True)
    )
    # Verified visits checked out after only a few minutes: flagged to the SC, never changed.
    short_s = config.short_visit_minutes * 60
    short_visits = Visit.objects.filter(
        user=user, state=VisitState.VERIFIED, checked_in_at__gte=lo, checked_out_at__isnull=False,
        time_on_site_s__lt=short_s,
    ).count()
    awaiting = Visit.objects.filter(
        user=user, state=VisitState.UNVERIFIED, resolved_by__isnull=True
    ).count()
    if p.paused:
        status = "paused"
    elif p.flagged:
        status = "over_threshold"
    elif awaiting:
        status = "unverified"
    else:
        status = "on_track"
    return {
        "user_id": str(user.id),
        "full_name": user.full_name,
        "role": user.role,
        **{k: v for k, v in asdict(p).items()},
        "worksites_visited": visited,
        "worksites_assigned": assigned,
        "median_time_on_site_s": int(statistics.median(durations)) if durations else None,
        "short_visits_4w": short_visits,
        "awaiting_review": awaiting,
        "status": status,
    }


def regional_quota(user: User, today: date, config=None) -> rules.RegionalQuota:
    config = config or ProgrammeConfig.get()
    return rules.regional_quota(verified_days(user, today, config), today, user.onboarded_on)


def national_quota(user: User, today: date, year=None, month=None, config=None) -> rules.NationalQuota:
    config = config or ProgrammeConfig.get()
    year, month = year or today.year, month or today.month
    # Include the following days so a mission starting this month is measured in full.
    horizon = min(today, date(year + (month == 12), month % 12 + 1, 1) + timedelta(days=40))
    return rules.national_quota(
        verified_days(user, horizon, config),
        year,
        month,
        today,
        config.working_days,
        config.national_at_risk_working_days,
    )


def worksite_scope(user: User):
    """Worksites a user may see and visit."""
    qs = Worksite.objects.filter(status=WorksiteStatus.ACTIVE).select_related("village", "commune", "trackable_object_instance")
    if user.role == Role.REGIONAL_SPECIALIST:
        return qs.filter(region_id=user.region_id)
    if user.role in (Role.NATIONAL_SPECIALIST, Role.RDP, Role.ADMIN):
        return qs
    if user.role == Role.SC:
        return qs.filter(commune_id=user.commune_id)
    return qs.filter(id__in=assigned_worksite_ids(user, clock.today()))


def last_verified_by_worksite(worksite_ids, user=None) -> dict:
    qs = Visit.objects.filter(worksite_id__in=worksite_ids, state=VisitState.VERIFIED)
    if user is not None:
        qs = qs.filter(user=user)
    latest = {}
    for worksite_id, checked_in_at in qs.values_list("worksite_id", "checked_in_at"):
        if worksite_id not in latest or checked_in_at > latest[worksite_id]:
            latest[worksite_id] = checked_in_at
    return latest
