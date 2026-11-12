"""Brice's production test (5 Nov 2026).

1. Check-in right after form 1, also offline: the phone checks in with the record's client uuid,
   and the server finds the site created from it (409 ``site_not_ready`` until form 1 arrives).
2. A visit started at the wrong site can be cancelled by the agent before check-out, with a
   reason. It is kept and shown to supervisors, but it is not a visit and never goes to review.
"""
import uuid

import pytest

from fieldmonitoring.registry.models import ProvisionalCoordinate
from fieldmonitoring.visits.models import Visit, VisitEvent, VisitState

from .conftest import BASE_LAT, BASE_LNG, north_of
from .test_subproject_forms import identification
from .test_visit_forms import agent, forms, push, record_item  # noqa: F401  (fixtures)

pytestmark = pytest.mark.django_db

CHECK_IN = "/api/v1/visits/check-in/"


def cancel(client_for, user, visit_id, note="Mauvais site choisi"):
    return client_for(user).post(f"/api/v1/visits/{visit_id}/cancel/", {"note": note}, format="json")


# --- Cancelling a visit started at the wrong site ------------------------------------------------


def test_agent_cancels_a_visit_started_at_the_wrong_site(ft, worksite, check_in, client_for):
    visit_id = check_in(ft, worksite).json()["id"]
    response = cancel(client_for, ft, visit_id)
    assert response.status_code == 200, response.content
    body = response.json()
    assert (body["state"], body["cancel_note"], body["awaiting_review"]) == ("cancelled", "Mauvais site choisi", False)
    assert body["cancelled_at"] is not None
    event = VisitEvent.objects.filter(visit_id=visit_id).last()
    assert (event.event, event.to_state, event.actor) == ("cancel", "cancelled", ft)
    # The agent is free again: no open visit.
    assert client_for(ft).get("/api/v1/me/visits/open/").data is None


def test_cancel_needs_a_reason(ft, worksite, check_in, client_for):
    visit_id = check_in(ft, worksite).json()["id"]
    assert cancel(client_for, ft, visit_id, note="  ").status_code in (400, 409)
    assert Visit.objects.get(pk=visit_id).state == VisitState.IN_PROGRESS


def test_failed_check_in_can_be_cancelled_and_leaves_the_review_queue(ft, sc, worksite, check_in, client_for):
    lat, lng = north_of(BASE_LAT, BASE_LNG, 500)
    visit_id = check_in(ft, worksite, lat=lat, lng=lng).json()["id"]
    assert cancel(client_for, ft, visit_id).status_code == 200
    queue = client_for(sc).get("/api/v1/review/queue/").json()
    assert visit_id not in str(queue)


def test_checked_out_visit_cannot_be_cancelled(ft, worksite, check_in, client_for):
    visit_id = check_in(ft, worksite).json()["id"]
    client_for(ft).post(f"/api/v1/visits/{visit_id}/check-out/", {"idempotency_key": "out-1"}, format="json")
    assert cancel(client_for, ft, visit_id).status_code == 409


def test_cancel_retried_from_the_queue_is_harmless(ft, worksite, check_in, client_for):
    visit_id = check_in(ft, worksite).json()["id"]
    assert cancel(client_for, ft, visit_id).status_code == 200
    assert cancel(client_for, ft, visit_id).status_code == 200
    assert VisitEvent.objects.filter(visit_id=visit_id, event="cancel").count() == 1


def test_only_the_agent_cancels_their_own_visit(ft, fc, worksite, check_in, client_for):
    visit_id = check_in(ft, worksite).json()["id"]
    assert cancel(client_for, fc, visit_id).status_code == 404


def test_cancelled_visit_withdraws_the_position_it_captured(sc, unmapped_worksite, check_in, client_for):
    visit_id = check_in(sc, unmapped_worksite).json()["id"]
    assert cancel(client_for, sc, visit_id).status_code == 200
    capture = ProvisionalCoordinate.objects.get(visit_id=visit_id)
    assert capture.status == "rejected"


def test_cancelled_visit_is_not_counted_as_a_visit(ft, sc, worksite, check_in, client_for):
    visit_id = check_in(ft, worksite).json()["id"]
    cancel(client_for, ft, visit_id)
    profile = client_for(sc).get(f"/api/v1/users/{ft.pk}/profile/").json()
    assert str(profile).count("'cancelled': 1") == 1
    site = client_for(sc).get(f"/api/v1/worksites/{worksite.id}/").json()
    assert site["visits"]["total"] == 0
    # Still in the agent's history, as a cancelled visit.
    history = client_for(sc).get(f"/api/v1/users/{ft.pk}/visits/").json()
    assert [v["state"] for v in history["results"]] == ["cancelled"]


def test_cancelled_visit_does_not_count_as_already_visited_today(ft, worksite, check_in, client_for):
    visit_id = check_in(ft, worksite).json()["id"]
    cancel(client_for, ft, visit_id)
    [mine] = [w for w in client_for(ft).get("/api/v1/me/worksites/").json() if w["id"] == str(worksite.id)]
    assert mine["my_visits_today"] == 0


def test_photo_arriving_after_the_cancel_is_kept(ft, worksite, capture, check_in, client_for):
    from .conftest import jpeg

    token = capture(ft, upload=False)
    visit_id = check_in(ft, worksite, capture_token=token).json()["id"]
    cancel(client_for, ft, visit_id)
    response = client_for(ft).post("/api/v1/photos/", {"capture_token": token, "file": jpeg()}, format="multipart")
    assert response.status_code == 201
    visit = Visit.objects.get(pk=visit_id)
    assert (visit.state, visit.photo_id is not None) == (VisitState.CANCELLED, True)


# --- Check-in at a site identified by form 1, possibly offline -------------------------------------


def check_in_by_record(client_for, capture, user, record_uuid, key=None):
    payload = {
        "record_client_uuid": record_uuid, "lat": BASE_LAT, "lng": BASE_LNG, "accuracy_m": 8,
        "capture_token": capture(user), "is_mock_location": False, "idempotency_key": key or str(uuid.uuid4()),
    }
    return client_for(user).post(CHECK_IN, payload, format="json")


def test_check_in_by_record_finds_the_site_created_by_form_1(forms, agent, village, capture, client_for):
    item = record_item(forms, identification(village))
    push(client_for, agent, item)
    response = check_in_by_record(client_for, capture, agent, item["client_uuid"])
    assert response.status_code == 201, response.content
    assert response.json()["worksite"]["name"] == "Forage de Séguéla"


def test_check_in_before_form_1_arrives_waits(forms, agent, village, capture, client_for):
    item = record_item(forms, identification(village))
    key = str(uuid.uuid4())
    response = check_in_by_record(client_for, capture, agent, item["client_uuid"], key=key)
    assert (response.status_code, response.json()["code"]) == (409, "site_not_ready")
    assert not Visit.objects.exists()
    # Form 1 arrives, the queue sends the check-in again with the same key.
    push(client_for, agent, item)
    assert check_in_by_record(client_for, capture, agent, item["client_uuid"], key=key).status_code == 201


def test_check_in_by_someone_elses_record_is_not_found(forms, agent, fc, village, capture, client_for):
    item = record_item(forms, identification(village))
    push(client_for, agent, item)
    assert check_in_by_record(client_for, capture, fc, item["client_uuid"]).status_code == 404


def test_check_in_needs_a_site_or_a_record(ft, capture, client_for):
    payload = {"capture_token": capture(ft), "idempotency_key": "k1", "lat": BASE_LAT, "lng": BASE_LNG}
    assert client_for(ft).post(CHECK_IN, payload, format="json").status_code == 400


# --- One position to confirm per sub-project site (Brice, 10 Nov) ---------------------------------


def test_check_in_after_form_1_adds_no_second_position(forms, agent, village, capture, client_for):
    item = record_item(forms, identification(village))
    push(client_for, agent, item)
    response = check_in_by_record(client_for, capture, agent, item["client_uuid"])
    # BR-9 still applies: no confirmed position, so the visit is unverified and goes to a human.
    assert response.json()["unverified_reason"] == "no_coordinate"
    [pending] = ProvisionalCoordinate.objects.filter(status="pending")
    # Form 1's position (accuracy 8 in the form), shown with this visit's photo as evidence.
    assert pending.accuracy_m == 8 and str(pending.visit_id) == response.json()["id"]
    # Cancelling the visit does not withdraw the position given in form 1.
    assert cancel(client_for, agent, response.json()["id"]).status_code == 200
    pending.refresh_from_db()
    assert pending.status == "pending" and pending.visit_id is None


def test_form_1_position_replaces_the_one_from_an_earlier_check_in(
    forms, agent, village, unmapped_worksite, check_in, client_for
):
    from fieldmonitoring.registry.models import WorksiteAssignment

    WorksiteAssignment.objects.create(user=agent, worksite=unmapped_worksite, assigned_on="2026-01-01")
    visit_id = check_in(agent, unmapped_worksite).json()["id"]
    push(client_for, agent, record_item(forms, identification(village), worksite_id=str(unmapped_worksite.pk)))
    assert ProvisionalCoordinate.objects.get(visit_id=visit_id, accuracy_m=12).status == "rejected"
    assert ProvisionalCoordinate.objects.filter(worksite=unmapped_worksite, status="pending").count() == 1


def test_plain_worksite_keeps_every_check_in_position(sc, ft, unmapped_worksite, check_in):
    from fieldmonitoring.registry.models import WorksiteAssignment

    WorksiteAssignment.objects.create(user=ft, worksite=unmapped_worksite, assigned_on="2026-01-01")
    for user in (sc, ft):
        assert check_in(user, unmapped_worksite).status_code == 201
    assert ProvisionalCoordinate.objects.filter(worksite=unmapped_worksite, status="pending").count() == 2


def test_api_answers_are_never_cached(ft, client_for, client):
    assert client.get("/api/v1/health/")["Cache-Control"] == "no-store, private"
    assert client_for(ft).get("/api/v1/me/worksites/")["Cache-Control"] == "no-store, private"
