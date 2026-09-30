"""Epic 2: check-in, photo, status, check-out. BR-9, BR-11, BR-12, BR-13, BR-7."""

import uuid

import pytest
import time_machine

from fieldmonitoring.registry.models import ProvisionalCoordinate
from fieldmonitoring.visits.models import Visit, VisitEvent
from tests.fieldmonitoring.conftest import BASE_LAT, BASE_LNG, jpeg, north_of, utc

pytestmark = pytest.mark.django_db


def test_br9_check_in_within_tolerance_is_in_progress(ft, worksite, check_in):
    lat, lng = north_of(BASE_LAT, BASE_LNG, 40)
    body = check_in(ft, worksite, lat=lat, lng=lng).json()
    assert body["state"] == "in_progress"
    assert body["unverified_reason"] is None
    assert 35 <= body["checkin"]["distance_m"] <= 45


def test_br9_too_far_is_unverified_but_not_blocked(ft, worksite, check_in):
    lat, lng = north_of(BASE_LAT, BASE_LNG, 180)
    response = check_in(ft, worksite, lat=lat, lng=lng)
    assert response.status_code == 201
    assert response.json()["state"] == "unverified"
    assert response.json()["unverified_reason"] == "location_failed"


def test_br9_poor_accuracy_is_location_failed(ft, worksite, check_in):
    assert check_in(ft, worksite, accuracy_m=150).json()["unverified_reason"] == "location_failed"


def test_br9_no_fix_is_location_failed(ft, worksite, check_in):
    body = check_in(ft, worksite, lat=None, lng=None, accuracy_m=None).json()
    assert body["unverified_reason"] == "location_failed"


def test_br9_null_coordinate_captures_provisional_position(sc, unmapped_worksite, check_in):
    body = check_in(sc, unmapped_worksite).json()
    assert body["unverified_reason"] == "no_coordinate"
    unmapped_worksite.refresh_from_db()
    assert unmapped_worksite.location is None  # not live until an admin confirms
    assert ProvisionalCoordinate.objects.filter(worksite=unmapped_worksite, status="pending").count() == 1


def test_br12_mock_location_is_unverified_with_flag(ft, worksite, check_in):
    body = check_in(ft, worksite, is_mock_location=True).json()
    assert body["unverified_reason"] == "mock_location"
    assert [f["kind"] for f in body["flags"]] == ["mock_location"]
    assert body["flags"][0]["detail"]["device_class"] == ft.device_class


def test_story_2_3_client_timestamp_is_ignored(ft, worksite, check_in):
    with time_machine.travel(utc(2026, 9, 28, 9, 0), tick=False):
        body = check_in(ft, worksite, checked_in_at="2020-01-01T00:00:00Z").json()
    assert body["checked_in_at"].startswith("2026-09-28T09:00")


def test_story_2_3_idempotency_key_replay_creates_one_visit(ft, worksite, capture, client_for):
    token = capture(ft)
    payload = {
        "worksite_id": str(worksite.id), "lat": BASE_LAT, "lng": BASE_LNG, "accuracy_m": 10,
        "capture_token": token, "idempotency_key": "abc-123",
    }
    client = client_for(ft)
    first = client.post("/api/v1/visits/check-in/", payload, format="json")
    second = client.post("/api/v1/visits/check-in/", payload, format="json")
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert Visit.objects.filter(user=ft).count() == 1


def test_facilitator_cannot_check_in_at_unassigned_worksite(ft, village, check_in):
    from fieldmonitoring.registry.models import Worksite

    other = Worksite.objects.create(name="Other", village=village, location=None)
    assert check_in(ft, other).status_code == 404


def test_story_2_6_check_out_verifies_and_derives_time_on_site(ft, worksite, check_in, client_for):
    with time_machine.travel(utc(2026, 9, 28, 8, 42), tick=False):
        visit_id = check_in(ft, worksite).json()["id"]
    client = client_for(ft)
    client.post(f"/api/v1/visits/{visit_id}/status/",
                {"works_progress": "on_schedule", "issue_reported": False}, format="json")
    with time_machine.travel(utc(2026, 9, 28, 9, 31), tick=False):
        body = client.post(f"/api/v1/visits/{visit_id}/check-out/",
                           {"lat": BASE_LAT, "lng": BASE_LNG, "idempotency_key": "out-1"},
                           format="json").json()
    assert body["state"] == "verified"
    assert body["time_on_site_s"] == 49 * 60
    assert body["status"]["works_progress"] == "on_schedule"


def test_story_2_6_check_out_on_failed_check_in_stays_unverified(ft, worksite, check_in, client_for):
    visit_id = check_in(ft, worksite, accuracy_m=500).json()["id"]
    body = client_for(ft).post(f"/api/v1/visits/{visit_id}/check-out/",
                               {"idempotency_key": "x"}, format="json").json()
    assert body["state"] == "unverified" and body["checked_out_at"] is not None


# --- Photos (Story 2.4, BR-11) --------------------------------------------------------


def test_br11_upload_without_valid_token_is_rejected(ft, client_for):
    response = client_for(ft).post(
        "/api/v1/photos/", {"capture_token": str(uuid.uuid4()), "file": jpeg()}, format="multipart"
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_capture_token"


def test_br11_token_cannot_be_reused(ft, client_for, capture):
    token = capture(ft)
    response = client_for(ft).post(
        "/api/v1/photos/", {"capture_token": token, "file": jpeg()}, format="multipart"
    )
    assert response.json()["code"] == "capture_token_used"


def test_br11_expired_unclaimed_token_is_rejected(ft, client_for):
    client = client_for(ft)
    with time_machine.travel(utc(2026, 9, 28, 8, 0), tick=False):
        token = client.post("/api/v1/photos/capture-token/").json()["token"]
    with time_machine.travel(utc(2026, 9, 28, 9, 0), tick=False):
        response = client.post("/api/v1/photos/", {"capture_token": token, "file": jpeg()}, format="multipart")
    assert response.json()["code"] == "capture_token_expired"


def test_story_2_4_photo_arriving_after_check_out_verifies_the_visit(ft, worksite, capture, check_in, client_for):
    token = capture(ft, upload=False)
    visit_id = check_in(ft, worksite, capture_token=token).json()["id"]
    client = client_for(ft)
    body = client.post(f"/api/v1/visits/{visit_id}/check-out/", {"idempotency_key": "o"}, format="json").json()
    assert body["state"] == "in_progress" and not body["has_photo"]  # pending photo
    client.post("/api/v1/photos/", {"capture_token": token, "file": jpeg()}, format="multipart")
    assert Visit.objects.get(pk=visit_id).state == "verified"


def test_br11_reused_photo_is_flagged_without_state_change(ft, worksite, check_in, client_for, capture):
    client = client_for(ft)
    first = check_in(ft, worksite, capture_token=capture(ft, pattern=3)).json()["id"]
    client.post(f"/api/v1/visits/{first}/check-out/", {"idempotency_key": "a"}, format="json")
    second = check_in(ft, worksite, capture_token=capture(ft, pattern=3)).json()
    assert second["state"] == "in_progress"
    assert "photo_reuse" in [f["kind"] for f in second["flags"]]


# --- BR-13 / BR-7 -------------------------------------------------------------------


def test_br13_impossible_travel_flags_the_later_visit(sc, worksite, village, check_in):
    from django.contrib.gis.geos import Point

    from fieldmonitoring.registry.models import Worksite

    far_lat, far_lng = north_of(BASE_LAT, BASE_LNG, 60_000)
    far = Worksite.objects.create(name="Far", village=village, location=Point(far_lng, far_lat, srid=4326))
    with time_machine.travel(utc(2026, 9, 28, 8, 0), tick=False):
        check_in(sc, worksite)
    with time_machine.travel(utc(2026, 9, 28, 8, 20), tick=False):
        body = check_in(sc, far, lat=far_lat, lng=far_lng).json()
    assert body["state"] == "in_progress"  # a flag, not a state change
    flag = next(f for f in body["flags"] if f["kind"] == "impossible_travel")
    assert flag["detail"]["speed_kmh"] > 120


def specialist_visits(user, worksite, check_in, client_for, capture):
    client = client_for(user)
    with time_machine.travel(utc(2026, 9, 10, 9, 0), tick=False):
        first = check_in(user, worksite, capture_token=capture(user, color=(10, 200, 30), pattern=5)).json()["id"]
        client.post(f"/api/v1/visits/{first}/check-out/", {"idempotency_key": "a"}, format="json")
    with time_machine.travel(utc(2026, 9, 28, 9, 0), tick=False):
        return check_in(user, worksite, capture_token=capture(user, color=(200, 20, 90), pattern=11)).json()


def test_br7_specialist_repeat_visit_is_flagged_not_blocked(regional, worksite, check_in, client_for, capture):
    body = specialist_visits(regional, worksite, check_in, client_for, capture)
    assert body["state"] == "in_progress"
    assert [f["kind"] for f in body["flags"]] == ["rotation_repeat"]


def test_br7_high_risk_repeat_is_not_flagged(regional, worksite, check_in, client_for, capture):
    worksite.is_high_risk = True
    worksite.save()
    body = specialist_visits(regional, worksite, check_in, client_for, capture)
    assert body["flags"] == []


def test_story_3_5_every_state_change_appends_an_audit_row(ft, worksite, check_in, client_for):
    visit_id = check_in(ft, worksite).json()["id"]
    client_for(ft).post(f"/api/v1/visits/{visit_id}/check-out/", {"idempotency_key": "a"}, format="json")
    events = list(VisitEvent.objects.filter(visit_id=visit_id).values_list("event", "to_state"))
    assert events == [("check_in_passed", "in_progress"), ("check_out", "verified")]
    with pytest.raises(Exception):
        VisitEvent.objects.filter(visit_id=visit_id).first().delete()


def test_story_2_5_old_app_builds_can_still_send_grievance_raised(ft, worksite, check_in, client_for):
    visit_id = check_in(ft, worksite).json()["id"]
    body = client_for(ft).post(
        f"/api/v1/visits/{visit_id}/status/",
        {"works_progress": "minor_delay", "grievance_raised": True},
        format="json",
    ).json()
    assert body["issue_reported"] is True and "grievance_raised" not in body


def test_story_2_5_issue_reported_is_required(ft, worksite, check_in, client_for):
    visit_id = check_in(ft, worksite).json()["id"]
    response = client_for(ft).post(
        f"/api/v1/visits/{visit_id}/status/", {"works_progress": "on_schedule"}, format="json"
    )
    assert response.status_code == 400
