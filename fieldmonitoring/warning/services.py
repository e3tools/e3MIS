"""BR-14: weekly warning generation. One generation, several filtered views (Story 5.5)."""

from collections import defaultdict
from datetime import date, timedelta

from django.db import transaction

from authorization.models import Role, User
from fieldmonitoring.compliance import rules, services as compliance
from fieldmonitoring.compliance.models import RoleThreshold
from fieldmonitoring.core import clock
from fieldmonitoring.core.models import ProgrammeConfig
from fieldmonitoring.registry.models import Worksite
from fieldmonitoring.visits.models import FlagKind, VisitFlag

from .models import EntryKind, Warning, WarningEntry


def _area(user: User) -> str:
    if user.commune_id:
        return user.commune.name
    if user.region_id:
        return user.region.name
    return "National" if user.role == Role.NATIONAL_SPECIALIST else ""


@transaction.atomic
def generate(week_of: date) -> Warning:
    """Generate (or regenerate, replacing) the warning issued on `week_of`.

    Covers the seven days ending the previous Sunday; evaluation is as of that Sunday.
    """
    config = ProgrammeConfig.get()
    thresholds = RoleThreshold.as_dict()
    period_end = week_of - timedelta(days=1)
    period_start = period_end - timedelta(days=6)
    active = User.objects.filter(is_active=True).select_related("commune", "region", "supervisor")
    field_staff = list(active.filter(role__in=["ft", "fc", "sc"]))

    previous = Warning.objects.filter(week_of__lt=week_of).order_by("-week_of").first()
    previous_days = (
        {
            (e.user_id, e.kind): e.days_since_last_verified
            for e in previous.entries.all()
        }
        if previous
        else {}
    )

    regularity, quota, rotation = [], [], []
    for user in field_staff:
        p = compliance.presence(user, period_end, config, thresholds)
        if p.flagged:
            regularity.append((user, p))
    regularity.sort(key=lambda item: item[1].days_since, reverse=True)

    for user in active.filter(role=Role.REGIONAL_SPECIALIST):
        q = compliance.regional_quota(user, period_end, config)
        if q.status in (rules.QuotaStatus.AT_RISK, rules.QuotaStatus.FAILING):
            quota.append((user, {
                "quota": "regional",
                "status": q.status.value,
                "visits_in_window": q.visits_in_window,
                "days_left": q.days_left,
                "due_by": q.due_by.isoformat(),
            }))
    for user in active.filter(role=Role.NATIONAL_SPECIALIST):
        months = {(period_end.year, period_end.month)}
        if period_start.month != period_end.month:
            months.add((period_start.year, period_start.month))  # report a month that just closed
        for year, month in sorted(months):
            q = compliance.national_quota(user, period_end, year, month, config)
            if q.status in (rules.QuotaStatus.AT_RISK, rules.QuotaStatus.FAILING):
                quota.append((user, {
                    "quota": "national",
                    "status": q.status.value,
                    "month": f"{year}-{month:02d}",
                    "longest_mission_days": q.longest_mission_days,
                    "field_days": q.field_days_in_month,
                    "remaining_working_days": q.remaining_working_days,
                }))

    lo, _ = clock.local_day_bounds(period_start, config)
    _, hi = clock.local_day_bounds(period_end, config)
    repeats = defaultdict(list)
    for flag in VisitFlag.objects.filter(
        kind=FlagKind.ROTATION_REPEAT, visit__checked_in_at__gte=lo, visit__checked_in_at__lt=hi
    ).select_related("visit__user", "visit__worksite"):
        repeats[flag.visit.user].append(flag.visit.worksite.name)
    for user, sites in repeats.items():
        rotation.append((user, {"count": len(sites), "worksites": sites}))

    warning, _ = Warning.objects.update_or_create(
        week_of=week_of,
        defaults={
            "period_start": period_start,
            "period_end": period_end,
            "generated_at": clock.now(),
            # Pausing never makes a person invisible (BR-4).
            "paused_count": sum(
                1 for u in active if compliance.current_pause(u, week_of) is not None
            ),
            "total_field_staff": len(field_staff),
            "overdue_high_risk_reviews": Worksite.objects.filter(
                is_high_risk=True, high_risk_review_due_on__lt=week_of
            ).count(),
            "thresholds": thresholds,
        },
    )
    warning.entries.all().delete()

    rank = 0
    rows = []
    for user, p in regularity:
        rank += 1
        prev = previous_days.get((user.id, EntryKind.REGULARITY))
        rows.append(WarningEntry(
            warning=warning, user=user, kind=EntryKind.REGULARITY, rank=rank,
            days_since_last_verified=p.days_since, threshold_days=p.threshold_days,
            delta_days=p.days_since - prev if prev is not None else None,
            detail={"new": previous is not None and prev is None},
        ))
    for kind, items in ((EntryKind.QUOTA, quota), (EntryKind.ROTATION, rotation)):
        for user, detail in items:
            rank += 1
            rows.append(WarningEntry(
                warning=warning, user=user, kind=kind, rank=rank, detail=detail,
            ))
    for row in rows:
        row.role = row.user.role
        row.supervisor = row.user.supervisor
        row.area = _area(row.user)
    WarningEntry.objects.bulk_create(rows)
    return warning


def entries_for(warning: Warning, viewer: User):
    """RdP and admin: the full list. SC: the same list filtered to their own team."""
    entries = warning.entries.select_related("user", "supervisor")
    if viewer.role == Role.SC:
        return entries.filter(supervisor=viewer)
    return entries
