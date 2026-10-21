"""Business rules from spec/docs/04-business-rules.md as pure functions.

Nothing in this module touches the database. Callers gather data and pass it in;
functions return verdicts. Every function names the rule it implements, and its
tests are named after the same rule ID.

Dates are programme-time calendar dates. Pauses are half-open ranges
[starts_on, ends_on): `ends_on` is the day the person is evaluated again.
"""

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from enum import StrEnum

DateRange = tuple[date, date]  # [start, end)

VERIFIED = "verified"
REGULARITY_ROLES = frozenset({"ft", "fc", "sc"})
SPECIALIST_ROLES = frozenset({"regional_specialist", "national_specialist"})


# --- BR-1 ---------------------------------------------------------------------


def field_days(visits: Iterable[tuple[str, datetime]], tz: tzinfo) -> set[date]:
    """BR-1: programme-time days with at least one verified visit, keyed on check-in."""
    return {checked_in_at.astimezone(tz).date() for state, checked_in_at in visits if state == VERIFIED}


# --- BR-2 / BR-4 ----------------------------------------------------------------


def is_paused_on(day: date, pauses: Sequence[DateRange]) -> bool:
    return any(start <= day < end for start, end in pauses)


def days_since_last_verified(
    last_verified: date | None,
    onboarded_on: date,
    today: date,
    pauses: Sequence[DateRange] = (),
) -> int:
    """BR-2: non-paused days after the last verified visit (or onboarding) up to today."""
    start = last_verified or onboarded_on
    if start >= today:
        return 0
    return sum(
        1
        for offset in range(1, (today - start).days + 1)
        if not is_paused_on(start + timedelta(days=offset), pauses)
    )


class PauseError(StrEnum):
    MISSING_END = "missing_end"
    END_BEFORE_START = "end_before_start"
    TOO_LONG = "too_long"
    MISSING_REASON = "missing_reason"
    SELF_PAUSE = "self_pause"
    NOT_ALLOWED = "not_allowed"


def validate_pause(
    starts_on: date, ends_on: date | None, reason: str | None, max_days: int
) -> PauseError | None:
    """BR-4: mandatory end date at most `max_days` after the start, mandatory reason."""
    if ends_on is None:
        return PauseError.MISSING_END
    if ends_on <= starts_on:
        return PauseError.END_BEFORE_START
    if (ends_on - starts_on).days > max_days:
        return PauseError.TOO_LONG
    if not (reason or "").strip():
        return PauseError.MISSING_REASON
    return None


def pause_permission(
    actor_role: str, actor_id, target_id, target_supervisor_id
) -> PauseError | None:
    """BR-4: RdP and admin pause anyone; an SC pauses their own team, never themselves."""
    if actor_id == target_id and actor_role == "sc":
        return PauseError.SELF_PAUSE
    if actor_role in {"rdp", "admin"}:
        return None
    if actor_role == "sc" and target_supervisor_id == actor_id:
        return None
    return PauseError.NOT_ALLOWED


# --- BR-3 -----------------------------------------------------------------------


def regularity_flagged(
    role: str, days_since: int, paused_today: bool, thresholds: Mapping[str, int]
) -> bool:
    """BR-3: flagged when not paused and days_since is strictly greater than the threshold."""
    if role not in REGULARITY_ROLES or role not in thresholds:
        return False
    return not paused_today and days_since > thresholds[role]


# --- BR-5 -----------------------------------------------------------------------


@dataclass(frozen=True)
class Mission:
    start: date
    end: date
    working_days: int


def missions(days: Collection[date], working_weekdays: Collection[int]) -> list[Mission]:
    """BR-5: maximal runs of field days, bridging a single non-field day."""
    ordered = sorted(set(days))
    runs: list[tuple[date, date]] = []
    for day in ordered:
        # A gap of exactly one non-field day (difference of 2) is bridged; two or more end it.
        if runs and (day - runs[-1][1]).days <= 2:
            runs[-1] = (runs[-1][0], day)
        else:
            runs.append((day, day))
    return [
        Mission(start, end, _count_working_days(start, end, working_weekdays)) for start, end in runs
    ]


def _count_working_days(start: date, end: date, working_weekdays: Collection[int]) -> int:
    return sum(
        1
        for offset in range((end - start).days + 1)
        if (start + timedelta(days=offset)).weekday() in working_weekdays
    )


class QuotaStatus(StrEnum):
    MET = "met"
    OK = "ok"
    AT_RISK = "at_risk"
    FAILING = "failing"


@dataclass(frozen=True)
class NationalQuota:
    year: int
    month: int
    status: QuotaStatus
    longest_mission_days: int
    field_days_in_month: int
    remaining_working_days: int


def _month_end(year: int, month: int) -> date:
    first_next = date(year + (month == 12), month % 12 + 1, 1)
    return first_next - timedelta(days=1)


def national_quota(
    days: Collection[date],
    year: int,
    month: int,
    today: date,
    working_weekdays: Collection[int],
    at_risk_working_days: int,
) -> NationalQuota:
    """BR-5: at least one mission of 5+ working days, counted in the month of its first day.

    `at_risk` is not defined by BR-5. We raise it when the month has fewer than
    `at_risk_working_days` working days left and no qualifying mission yet.
    """
    in_month = [m for m in missions(days, working_weekdays) if (m.start.year, m.start.month) == (year, month)]
    longest = max((m.working_days for m in in_month), default=0)
    month_end = _month_end(year, month)
    remaining = (
        _count_working_days(max(today, date(year, month, 1)), month_end, working_weekdays)
        if today <= month_end
        else 0
    )
    if longest >= 5:
        status = QuotaStatus.MET
    elif today > month_end:
        status = QuotaStatus.FAILING
    elif remaining < at_risk_working_days:
        status = QuotaStatus.AT_RISK
    else:
        status = QuotaStatus.OK
    field_in_month = sum(1 for d in days if (d.year, d.month) == (year, month))
    return NationalQuota(year, month, status, longest, field_in_month, remaining)


# --- BR-6 -----------------------------------------------------------------------

REGIONAL_WINDOW_DAYS = 14
REGIONAL_AT_RISK_DAYS = 4


@dataclass(frozen=True)
class RegionalQuota:
    status: QuotaStatus
    window_start: date
    window_end: date
    visits_in_window: int
    last_verified_on: date | None
    due_by: date
    days_left: int
    history_met: int
    history_missed: int


def regional_quota(
    verified_dates: Collection[date], today: date, onboarded_on: date, history_windows: int = 6
) -> RegionalQuota:
    """BR-6: at least one verified visit in the trailing 14 days, evaluated daily.

    `due_by` is the last day the most recent visit (or onboarding) still falls inside
    the trailing window. `at_risk` when 4 or fewer days are left without a newer visit.
    """
    window_start = today - timedelta(days=REGIONAL_WINDOW_DAYS - 1)
    past = [d for d in verified_dates if d <= today]
    last = max(past, default=None)
    anchor = last or onboarded_on
    due_by = anchor + timedelta(days=REGIONAL_WINDOW_DAYS - 1)
    days_left = max((due_by - today).days + 1, 0)
    in_window = sum(1 for d in past if d >= window_start)
    if days_left == 0:
        status = QuotaStatus.FAILING
    elif days_left <= REGIONAL_AT_RISK_DAYS:
        status = QuotaStatus.AT_RISK
    else:
        status = QuotaStatus.OK

    met = missed = 0
    for k in range(1, history_windows + 1):
        block_end = window_start - timedelta(days=REGIONAL_WINDOW_DAYS * (k - 1) + 1)
        block_start = block_end - timedelta(days=REGIONAL_WINDOW_DAYS - 1)
        if block_end < onboarded_on:
            break
        if any(block_start <= d <= block_end for d in past):
            met += 1
        else:
            missed += 1
    return RegionalQuota(status, window_start, today, in_window, last, due_by, days_left, met, missed)


# --- BR-7 -----------------------------------------------------------------------


def rotation_repeat(
    role: str,
    worksite_is_high_risk: bool,
    checkin_day: date,
    earlier_verified_days_same_site: Iterable[date],
    window_days: int,
) -> date | None:
    """BR-7: the date of the earlier verified visit that makes this a rotation repeat, if any.

    Informational only: never blocks a check-in and never changes visit state.
    """
    if role not in SPECIALIST_ROLES or worksite_is_high_risk:
        return None
    recent = [d for d in earlier_verified_days_same_site if 0 <= (checkin_day - d).days <= window_days]
    return max(recent, default=None)


# --- BR-9 / BR-12 ---------------------------------------------------------------


def location_check(
    *,
    is_mock: bool,
    has_position: bool,
    worksite_has_coordinate: bool,
    accuracy_m: float | None,
    distance_m: float | None,
    tolerance_m: int,
    max_accuracy_m: int,
) -> str | None:
    """BR-9 (with BR-12 first): the unverified reason, or None when the check passes."""
    if is_mock:
        return "mock_location"
    if not worksite_has_coordinate:
        return "no_coordinate"
    if not has_position or accuracy_m is None or distance_m is None:
        return "location_failed"
    if accuracy_m > max_accuracy_m:
        return "location_failed"
    if distance_m > tolerance_m:
        return "location_failed"
    return None


# --- BR-13 ----------------------------------------------------------------------


def implied_speed_kmh(distance_m: float, seconds: float) -> float:
    if seconds <= 0:
        return float("inf") if distance_m > 0 else 0.0
    return (distance_m / 1000) / (seconds / 3600)


def impossible_travel(distance_m: float, seconds: float, limit_kmh: float) -> bool:
    """BR-13: implied speed between consecutive check-ins above the limit. A flag only."""
    return implied_speed_kmh(distance_m, seconds) > limit_kmh
