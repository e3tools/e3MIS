"""One test (at least) per business rule, named for its rule ID. Pure functions only."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fieldmonitoring.compliance import rules
from fieldmonitoring.compliance.rules import PauseError, QuotaStatus

D = date
MON_FRI = {0, 1, 2, 3, 4}
ABIDJAN = ZoneInfo("Africa/Abidjan")


def run(start: date, n: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


# --- BR-1 ---------------------------------------------------------------------------


def test_br1_only_verified_visits_make_a_field_day():
    visits = [
        ("verified", datetime(2026, 9, 1, 9, tzinfo=UTC)),
        ("unverified", datetime(2026, 9, 2, 9, tzinfo=UTC)),
        ("missed", datetime(2026, 9, 3, 9, tzinfo=UTC)),
    ]
    assert rules.field_days(visits, ABIDJAN) == {D(2026, 9, 1)}


def test_br1_overnight_visit_counts_on_check_in_day_in_programme_time():
    paris = ZoneInfo("Europe/Paris")
    # 23:50 Paris on 1 Sep is 21:50 UTC; the field day is 1 Sep in programme time.
    visits = [("verified", datetime(2026, 9, 1, 21, 50, tzinfo=UTC))]
    assert rules.field_days(visits, paris) == {D(2026, 9, 1)}
    # The same instant is 2 Sep in a zone ahead of UTC by more than 2h10.
    assert rules.field_days(visits, ZoneInfo("Asia/Dubai")) == {D(2026, 9, 2)}


# --- BR-2 ---------------------------------------------------------------------------


def test_br2_no_visits_ever_counts_from_onboarding():
    assert rules.days_since_last_verified(None, D(2026, 9, 1), D(2026, 9, 11)) == 10


def test_br2_verified_visit_today_is_zero():
    assert rules.days_since_last_verified(D(2026, 9, 11), D(2026, 1, 1), D(2026, 9, 11)) == 0


def test_br2_pause_spanning_the_entire_gap():
    pauses = [(D(2026, 9, 2), D(2026, 9, 12))]
    assert rules.days_since_last_verified(D(2026, 9, 1), D(2026, 1, 1), D(2026, 9, 11), pauses) == 0


def test_br2_pause_partially_overlapping_the_gap():
    # Gap 2..11 Sep is 10 days; paused 5..8 Sep (4 days) -> 6.
    pauses = [(D(2026, 9, 5), D(2026, 9, 9))]
    assert rules.days_since_last_verified(D(2026, 9, 1), D(2026, 1, 1), D(2026, 9, 11), pauses) == 6


def test_br2_pause_that_ended_yesterday():
    # Paused 1..9 Sep, resumed 10 Sep; today is 10 Sep, last visit 31 Aug.
    pauses = [(D(2026, 9, 1), D(2026, 9, 10))]
    assert rules.days_since_last_verified(D(2026, 8, 31), D(2026, 1, 1), D(2026, 9, 10), pauses) == 1


def test_br2_returning_from_14_days_leave_is_not_instantly_flagged():
    last = D(2026, 9, 1)
    pauses = [(D(2026, 9, 3), D(2026, 9, 17))]
    since = rules.days_since_last_verified(last, D(2026, 1, 1), D(2026, 9, 17), pauses)
    assert since == 2
    assert not rules.regularity_flagged("fc", since, False, {"fc": 10})


# --- BR-3 ---------------------------------------------------------------------------


def test_br3_strictly_greater_than_threshold():
    assert not rules.regularity_flagged("ft", 10, False, {"ft": 10})
    assert rules.regularity_flagged("ft", 11, False, {"ft": 10})


def test_br3_paused_user_is_not_flagged():
    assert not rules.regularity_flagged("sc", 40, True, {"sc": 14})


def test_br3_specialists_and_rdp_are_not_evaluated():
    thresholds = {"ft": 10, "regional_specialist": 1, "rdp": 1}
    assert not rules.regularity_flagged("regional_specialist", 99, False, thresholds)
    assert not rules.regularity_flagged("rdp", 99, False, thresholds)


# --- BR-4 ---------------------------------------------------------------------------


def test_br4_pause_needs_an_end_date():
    assert rules.validate_pause(D(2026, 9, 1), None, "leave", 30) == PauseError.MISSING_END


def test_br4_pause_longer_than_30_days_is_rejected():
    assert rules.validate_pause(D(2026, 9, 1), D(2026, 10, 2), "leave", 30) == PauseError.TOO_LONG
    assert rules.validate_pause(D(2026, 9, 1), D(2026, 10, 1), "leave", 30) is None


def test_br4_pause_needs_a_reason():
    assert rules.validate_pause(D(2026, 9, 1), D(2026, 9, 5), "  ", 30) == PauseError.MISSING_REASON


def test_br4_sc_cannot_pause_themselves():
    assert rules.pause_permission("sc", 1, 1, None) == PauseError.SELF_PAUSE


def test_br4_sc_pauses_own_team_only():
    assert rules.pause_permission("sc", 1, 2, 1) is None
    assert rules.pause_permission("sc", 1, 3, 9) == PauseError.NOT_ALLOWED
    assert rules.pause_permission("rdp", 1, 3, 9) is None
    assert rules.pause_permission("admin", 1, 3, None) is None
    assert rules.pause_permission("ft", 1, 3, None) == PauseError.NOT_ALLOWED


def test_br4_pause_is_half_open_so_the_end_day_is_evaluated():
    pauses = [(D(2026, 9, 1), D(2026, 9, 10))]
    assert rules.is_paused_on(D(2026, 9, 9), pauses)
    assert not rules.is_paused_on(D(2026, 9, 10), pauses)


# --- BR-5 ---------------------------------------------------------------------------


def national(days, today=D(2026, 9, 30), year=2026, month=9):
    return rules.national_quota(days, year, month, today, MON_FRI, 10)


def test_br5_exactly_five_working_days_is_satisfied():
    q = national(run(D(2026, 9, 7), 5))  # Mon 7 – Fri 11
    assert q.status == QuotaStatus.MET and q.longest_mission_days == 5


def test_br5_one_travel_day_inside_the_run_is_bridged():
    days = [D(2026, 9, 7), D(2026, 9, 9), D(2026, 9, 10), D(2026, 9, 11)]  # Tue 8 is travel
    assert national(days).status == QuotaStatus.MET


def test_br5_two_consecutive_non_field_days_split_the_mission():
    # Mon 7, Tue 8, then Wed 9 and Thu 10 off, then Fri 11 – Mon 14: two short missions.
    days = [D(2026, 9, 7), D(2026, 9, 8), D(2026, 9, 11), D(2026, 9, 12), D(2026, 9, 13), D(2026, 9, 14)]
    missions = rules.missions(days, MON_FRI)
    assert len(missions) == 2
    assert national(days).status != QuotaStatus.MET


def test_br5_mission_spanning_month_end_counts_to_its_first_month():
    days = run(D(2026, 9, 29), 7)  # Tue 29 Sep – Mon 5 Oct: 5 working days
    assert national(days, today=D(2026, 10, 6)).status == QuotaStatus.MET
    october = rules.national_quota(days, 2026, 10, D(2026, 10, 6), MON_FRI, 10)
    assert october.status != QuotaStatus.MET


def test_br5_month_over_without_mission_is_failing():
    assert national(run(D(2026, 9, 7), 3), today=D(2026, 10, 1)).status == QuotaStatus.FAILING


def test_br5_at_risk_late_in_the_month():
    assert national([], today=D(2026, 9, 24)).status == QuotaStatus.AT_RISK
    assert national([], today=D(2026, 9, 2)).status == QuotaStatus.OK


# --- BR-6 ---------------------------------------------------------------------------


def test_br6_visit_in_trailing_14_days_satisfies():
    q = rules.regional_quota({D(2026, 9, 20)}, D(2026, 9, 25), D(2026, 1, 1))
    assert q.status == QuotaStatus.OK and q.visits_in_window == 1


def test_br6_window_is_rolling_not_fixed():
    # Visit 14 days ago (inclusive window start) still counts; 15 days ago does not.
    today = D(2026, 9, 30)
    assert rules.regional_quota({today - timedelta(days=13)}, today, D(2026, 1, 1)).status != QuotaStatus.FAILING
    assert rules.regional_quota({today - timedelta(days=14)}, today, D(2026, 1, 1)).status == QuotaStatus.FAILING


def test_br6_at_risk_with_four_or_fewer_days_left():
    today = D(2026, 9, 30)
    assert rules.regional_quota({today - timedelta(days=9)}, today, D(2026, 1, 1)).status == QuotaStatus.OK
    q = rules.regional_quota({today - timedelta(days=10)}, today, D(2026, 1, 1))
    assert q.status == QuotaStatus.AT_RISK and q.days_left == 4


def test_br6_new_specialist_gets_a_full_window_from_onboarding():
    q = rules.regional_quota(set(), D(2026, 9, 3), D(2026, 9, 1))
    assert q.status == QuotaStatus.OK and q.days_left == 12


# --- BR-7 ---------------------------------------------------------------------------


def test_br7_repeat_within_30_days_by_specialist():
    assert rules.rotation_repeat("regional_specialist", False, D(2026, 9, 30), [D(2026, 9, 21)], 30) == D(2026, 9, 21)


def test_br7_high_risk_sites_are_exempt():
    assert rules.rotation_repeat("national_specialist", True, D(2026, 9, 30), [D(2026, 9, 21)], 30) is None


def test_br7_only_specialists_and_only_within_window():
    assert rules.rotation_repeat("ft", False, D(2026, 9, 30), [D(2026, 9, 21)], 30) is None
    assert rules.rotation_repeat("regional_specialist", False, D(2026, 9, 30), [D(2026, 8, 30)], 30) is None


# --- BR-9 / BR-12 ---------------------------------------------------------------------


def check(**overrides):
    args = dict(
        is_mock=False, has_position=True, worksite_has_coordinate=True,
        accuracy_m=10, distance_m=40, tolerance_m=100, max_accuracy_m=100,
    )
    args.update(overrides)
    return rules.location_check(**args)


def test_br9_passes_within_tolerance():
    assert check() is None
    assert check(distance_m=100, accuracy_m=100) is None  # boundaries are inclusive


def test_br9_null_coordinate():
    assert check(worksite_has_coordinate=False) == "no_coordinate"


def test_br9_accuracy_too_poor():
    assert check(accuracy_m=101) == "location_failed"


def test_br9_too_far():
    assert check(distance_m=101) == "location_failed"


def test_br9_no_position_fix():
    assert check(has_position=False, accuracy_m=None, distance_m=None) == "location_failed"


def test_br12_mock_location_takes_precedence():
    assert check(is_mock=True, worksite_has_coordinate=False) == "mock_location"


# --- BR-13 ----------------------------------------------------------------------------


def test_br13_implied_speed_above_limit():
    assert rules.impossible_travel(50_000, 600, 120)  # 50 km in 10 min
    assert not rules.impossible_travel(10_000, 600, 120)  # 60 km/h
    assert rules.impossible_travel(5_000, 0, 120)
    assert not rules.impossible_travel(0, 0, 120)
