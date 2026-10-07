"""Epic 5 and Epic 6: presence, team view, pauses, weekly warning, thresholds, hierarchy."""

from datetime import date, timedelta

import pytest
import time_machine
from django.core.exceptions import ValidationError

from authorization.models import Role
from fieldmonitoring.compliance import services as compliance
from fieldmonitoring.compliance.models import Pause
from fieldmonitoring.core.jobs import warning_if_due
from fieldmonitoring.registry.models import WorksiteAssignment
from fieldmonitoring.warning.models import Warning
from fieldmonitoring.warning.services import entries_for, generate
from tests.fieldmonitoring.conftest import make_user, utc

pytestmark = pytest.mark.django_db


def verified_visit(user, worksite, check_in, client_for, at):
    with time_machine.travel(at, tick=False):
        visit_id = check_in(user, worksite).json()["id"]
        client_for(user).post(f"/api/v1/visits/{visit_id}/check-out/", {"idempotency_key": visit_id}, format="json")
    return visit_id


# --- Story 1.1 ------------------------------------------------------------------------


def test_story_1_1_ft_with_supervisor_in_other_commune_is_rejected(other_sc, commune):
    with pytest.raises(ValidationError):
        make_user("x", Role.FT, supervisor=other_sc, commune=commune)


def test_story_1_1_sc_cannot_have_a_supervisor(sc, commune):
    with pytest.raises(ValidationError):
        make_user("y", Role.SC, supervisor=sc, commune=commune)


def test_story_1_1_deactivated_user_leaves_evaluation_but_keeps_visits(ft, worksite, check_in, client_for):
    verified_visit(ft, worksite, check_in, client_for, utc(2026, 8, 1, 9))
    ft.is_active = False
    ft.save()
    warning = generate(date(2026, 9, 28))
    assert not warning.entries.filter(user=ft).exists()
    assert ft.visits.count() == 1


# --- Story 1.4 --------------------------------------------------------------------------


def test_story_1_4_coverage_uses_assignments_in_force_that_week(ft, worksite, village, config):
    from fieldmonitoring.registry.models import Worksite

    later = Worksite.objects.create(name="Later", village=village)
    WorksiteAssignment.objects.create(user=ft, worksite=later, assigned_on=date(2026, 9, 20))
    WorksiteAssignment.objects.filter(user=ft, worksite=worksite).update(unassigned_on=date(2026, 9, 25))
    assert compliance.coverage(ft, date(2026, 9, 1), date(2026, 9, 7), config) == (0, 1)
    _, assigned_now = compliance.coverage(ft, date(2026, 9, 21), date(2026, 9, 27), config)
    assert assigned_now == 1  # only "Later" is in force on 27 Sep


# --- Story 5.1 / 5.2 ----------------------------------------------------------------------


def test_story_5_1_presence_counts_from_last_verified_visit(ft, worksite, check_in, client_for):
    verified_visit(ft, worksite, check_in, client_for, utc(2026, 9, 20, 9))
    p = compliance.presence(ft, date(2026, 9, 28))
    assert p.days_since == 8 and p.threshold_days == 10 and not p.flagged
    assert p.verified_last_4_weeks == 1


def test_story_5_1_unverified_visit_does_not_reset_the_count(ft, worksite, check_in):
    with time_machine.travel(utc(2026, 9, 27, 9), tick=False):
        check_in(ft, worksite, accuracy_m=999)
    assert compliance.presence(ft, date(2026, 9, 28)).last_verified_on is None


def test_story_6_2_on_the_day_a_pause_ends_user_is_evaluated_with_paused_days_excluded(ft, sc):
    ft.onboarded_on = date(2026, 9, 1)
    ft.save()
    Pause.objects.create(user=ft, starts_on=date(2026, 9, 5), ends_on=date(2026, 9, 25), reason="Congé", set_by=sc)
    assert compliance.presence(ft, date(2026, 9, 24)).paused
    p = compliance.presence(ft, date(2026, 9, 25))
    assert not p.paused and p.days_since == 4  # 2, 3, 4 Sep and 25 Sep


# --- Pause API (BR-4, Story 6.2) ---------------------------------------------------------


def pause(client, user, **data):
    payload = {"starts_on": "2026-10-01", "ends_on": "2026-10-10", "reason": "Congé annuel", **data}
    return client.post(f"/api/v1/users/{user.id}/pauses/", payload, format="json")


def test_br4_31_day_pause_is_rejected(sc, ft, client_for):
    response = pause(client_for(sc), ft, ends_on="2026-11-01")
    assert response.status_code == 400 and response.json()["code"] == "too_long"


def test_br4_open_ended_pause_is_rejected(sc, ft, client_for):
    assert pause(client_for(sc), ft, ends_on=None).status_code == 400


def test_br4_sc_pausing_themselves_is_rejected(sc, client_for):
    assert pause(client_for(sc), sc).json()["code"] == "self_pause"


def test_br4_sc_cannot_pause_another_team(other_sc, ft, client_for):
    assert pause(client_for(other_sc), ft).status_code == 403


def test_br4_pause_records_who_and_is_cancelled_not_deleted(sc, ft, client_for):
    body = pause(client_for(sc), ft).json()
    assert body["set_by"] == sc.full_name
    client_for(sc).post(f"/api/v1/pauses/{body['id']}/cancel/")
    stored = Pause.objects.get(pk=body["id"])
    assert stored.cancelled_at is not None
    with pytest.raises(RuntimeError):
        stored.delete()


# --- Story 5.3 --------------------------------------------------------------------------


def test_story_5_3_team_view_shows_paused_people(sc, ft, fc, client_for):
    Pause.objects.create(user=fc, starts_on=date(2026, 9, 1), ends_on=date(2026, 10, 1), reason="Congé", set_by=sc)
    with time_machine.travel(utc(2026, 9, 28, 9), tick=False):
        body = client_for(sc).get("/api/v1/team/presence/").json()
    statuses = {row["full_name"]: row["status"] for row in body["rows"]}
    assert statuses[fc.full_name] == "paused"
    assert body["stats"]["paused"] == 1
    assert body["thresholds"] == {"fc": 10, "ft": 10}


def test_story_5_3_team_row_counts_short_visits(sc, ft, worksite, check_in, client_for):
    for day, minutes in ((22, 2), (23, 3), (24, 40)):
        with time_machine.travel(utc(2026, 9, day, 8, 0), tick=False):
            visit_id = check_in(ft, worksite).json()["id"]
        with time_machine.travel(utc(2026, 9, day, 8, minutes), tick=False):
            client_for(ft).post(f"/api/v1/visits/{visit_id}/check-out/", {"idempotency_key": visit_id}, format="json")
    with time_machine.travel(utc(2026, 9, 28, 9), tick=False):
        body = client_for(sc).get("/api/v1/team/presence/").json()
    row = next(r for r in body["rows"] if r["full_name"] == ft.full_name)
    assert row["short_visits_4w"] == 2


# --- BR-14 / Story 5.4 / 5.5 ----------------------------------------------------------------


@pytest.fixture
def lapsed_team(sc, ft, fc, worksite, check_in, client_for):
    sc.onboarded_on = date(2026, 9, 20)  # the SC themselves is not lapsed in these tests
    sc.save()
    verified_visit(ft, worksite, check_in, client_for, utc(2026, 9, 1, 9))  # 26 days by 27 Sep
    Pause.objects.create(user=fc, starts_on=date(2026, 9, 1), ends_on=date(2026, 10, 15), reason="Congé", set_by=sc)
    return ft, fc


def test_br14_paused_user_counted_not_flagged(lapsed_team):
    ft, fc = lapsed_team
    warning = generate(date(2026, 9, 28))
    flagged = list(warning.entries.filter(kind="regularity").values_list("user_id", flat=True))
    assert ft.id in flagged and fc.id not in flagged
    assert warning.paused_count == 1


def test_br14_regeneration_is_idempotent(lapsed_team):
    generate(date(2026, 9, 28))
    warning = generate(date(2026, 9, 28))
    assert Warning.objects.count() == 1
    assert warning.entries.filter(kind="regularity").count() == 1


def test_br14_ranked_by_days_since_with_threshold_inline(lapsed_team, sc, commune):
    other = make_user("salif", Role.FT, supervisor=sc, commune=commune, onboarded_on=date(2026, 9, 10))
    entries = list(generate(date(2026, 9, 28)).entries.filter(kind="regularity"))
    assert [e.user_id for e in entries] == [lapsed_team[0].id, other.id]
    assert entries[0].days_since_last_verified == 26 and entries[0].threshold_days == 10


def test_br14_week_on_week_delta(lapsed_team):
    generate(date(2026, 9, 21))
    entry = generate(date(2026, 9, 28)).entries.get(kind="regularity")
    assert entry.delta_days == 7


def test_story_5_5_sc_sees_same_list_filtered_and_own_entry_goes_to_rdp(lapsed_team, sc, rdp):
    sc.onboarded_on = date(2026, 8, 1)
    sc.save()
    warning = generate(date(2026, 9, 28))
    sc_view = {e.user_id for e in entries_for(warning, sc)}
    rdp_view = {e.user_id for e in entries_for(warning, rdp)}
    assert lapsed_team[0].id in sc_view and sc.id not in sc_view
    assert sc.id in rdp_view and sc_view <= rdp_view


def test_br14_quota_entries_for_specialists(regional):
    regional.onboarded_on = date(2026, 8, 1)
    regional.save()
    entry = generate(date(2026, 9, 28)).entries.get(kind="quota")
    assert entry.detail["quota"] == "regional" and entry.detail["status"] == "failing"


@pytest.mark.parametrize(
    "monday_0600_utc",
    [utc(2026, 10, 19, 4, 0), utc(2026, 10, 26, 5, 0)],  # Paris summer (UTC+2) / winter (UTC+1)
)
def test_br14_generated_monday_0600_programme_time_across_dst(config, monday_0600_utc):
    config.timezone = "Europe/Paris"
    config.save()
    assert warning_if_due(monday_0600_utc - timedelta(minutes=1)) is None
    warning = warning_if_due(monday_0600_utc)
    assert warning is not None and warning.week_of.weekday() == 0
    assert warning.period_end == warning.week_of - timedelta(days=1)


def test_dec6_warning_has_no_acknowledgement_fields():
    names = {f.name for f in Warning._meta.get_fields()}
    assert not names & {"acknowledged", "acknowledged_by", "handled", "status", "action"}


# --- Story 6.1 --------------------------------------------------------------------------


def test_story_6_1_threshold_change_is_audited_and_admin_only(admin_user, sc, client_for):
    from fieldmonitoring.core.models import ConfigChange

    assert client_for(sc).put("/api/v1/config/thresholds/", [{"role": "ft", "days": 7}], format="json").status_code == 403
    body = client_for(admin_user).put("/api/v1/config/thresholds/", [{"role": "ft", "days": 7}], format="json").json()
    assert {t["role"]: t["days"] for t in body}["ft"] == 7
    assert ConfigChange.objects.get(key="threshold.ft").new_value == "7"


def test_story_6_1_change_does_not_alter_stored_warnings(admin_user, lapsed_team, client_for):
    warning = generate(date(2026, 9, 28))
    client_for(admin_user).put("/api/v1/config/thresholds/", [{"role": "ft", "days": 40}], format="json")
    entry = warning.entries.get(kind="regularity")
    assert entry.threshold_days == 10


# --- Exports and scoped totals ----------------------------------------------------------


def test_story_5_4_warning_csv_export(lapsed_team, rdp, client_for):
    generate(date(2026, 9, 28))
    response = client_for(rdp).get("/api/v1/warnings/2026-09-28/?format=csv")
    assert response.status_code == 200 and response["Content-Type"] == "text/csv"
    assert "Ibrahim" in response.content.decode()


def test_story_5_6_baseline_csv_export(lapsed_team, rdp, client_for):
    response = client_for(rdp).get("/api/v1/compliance/baseline/?weeks=2&format=csv")
    assert response.status_code == 200 and response.content.decode().startswith("week_ending")


def test_story_5_5_sc_totals_are_scoped_to_team(lapsed_team, sc, client_for):
    generate(date(2026, 9, 28))
    body = client_for(sc).get("/api/v1/warnings/2026-09-28/").json()
    assert body["total_field_staff"] == 2 and body["paused_count"] == 1
    assert body["entries"][0]["supervisor_id"] == str(sc.id)


def test_story_5_3_rdp_team_view_scopes_tiles_to_chosen_supervisor(sc, other_sc, ft, worksite, check_in, rdp, client_for):
    check_in(ft, worksite, accuracy_m=500)
    body = client_for(rdp).get(f"/api/v1/team/presence/?supervisor={sc.id}").json()
    assert body["stats"]["awaiting_review"] == 1
    other = client_for(rdp).get(f"/api/v1/team/presence/?supervisor={other_sc.id}").json()
    assert other["stats"]["awaiting_review"] == 0
