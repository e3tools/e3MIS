"""BR-10 / Story 3.4: review queue scoping and resolution."""

import pytest
import time_machine

from fieldmonitoring.visits.models import Visit
from tests.fieldmonitoring.conftest import make_user, utc

pytestmark = pytest.mark.django_db


@pytest.fixture
def unverified(ft, worksite, check_in):
    return check_in(ft, worksite, accuracy_m=500).json()["id"]


def test_story_3_4_sc_sees_own_team_queue(sc, unverified, client_for):
    ids = [v["id"] for v in client_for(sc).get("/api/v1/review/queue/").json()]
    assert ids == [unverified]


def test_story_3_4_other_sc_cannot_see_or_resolve(other_sc, unverified, client_for):
    client = client_for(other_sc)
    assert client.get("/api/v1/review/queue/").json() == []
    response = client.post(f"/api/v1/review/{unverified}/", {"resolution": "missed"}, format="json")
    assert response.status_code == 403


def test_br10_sc_own_visit_routes_to_rdp(sc, rdp, unmapped_worksite, check_in, client_for):
    visit_id = check_in(sc, unmapped_worksite).json()["id"]
    assert client_for(sc).get("/api/v1/review/queue/").json() == []
    assert [v["id"] for v in client_for(rdp).get("/api/v1/review/queue/").json()] == [visit_id]
    response = client_for(sc).post(f"/api/v1/review/{visit_id}/", {"resolution": "verified"}, format="json")
    assert response.status_code == 403


def test_br10_resolution_records_actor_time_and_note(sc, unverified, client_for):
    with time_machine.travel(utc(2026, 9, 29, 10, 0), tick=False):
        body = client_for(sc).post(
            f"/api/v1/review/{unverified}/", {"resolution": "missed", "note": "Not there"}, format="json"
        ).json()
    assert body["state"] == "missed"
    visit = Visit.objects.get(pk=unverified)
    assert visit.resolved_by == visit.user.supervisor
    assert visit.resolved_at == utc(2026, 9, 29, 10, 0)
    assert visit.resolution_note == "Not there"


def test_br10_accepting_makes_the_visit_verified(sc, unverified, client_for):
    body = client_for(sc).post(f"/api/v1/review/{unverified}/", {"resolution": "verified"}, format="json").json()
    assert body["state"] == "verified" and body["unverified_reason"] is None


def test_story_3_4_mock_location_needs_a_note(sc, ft, worksite, check_in, client_for):
    visit_id = check_in(ft, worksite, is_mock_location=True).json()["id"]
    client = client_for(sc)
    assert client.post(f"/api/v1/review/{visit_id}/", {"resolution": "verified"}, format="json").status_code == 400
    ok = client.post(f"/api/v1/review/{visit_id}/", {"resolution": "verified", "note": "Called, GPS app"}, format="json")
    assert ok.status_code == 200


def test_story_3_4_nothing_happens_after_72_hours(sc, ft, worksite, check_in):
    from fieldmonitoring.core.jobs import run_due_jobs

    with time_machine.travel(utc(2026, 9, 28, 9, 0), tick=False):
        visit_id = check_in(ft, worksite, accuracy_m=500).json()["id"]
    run_due_jobs(utc(2026, 10, 2, 21, 0))
    visit = Visit.objects.get(pk=visit_id)
    assert visit.state == "unverified" and visit.resolved_by is None


def test_story_2_8_field_user_gives_reason(ft, unverified, client_for):
    body = client_for(ft).post(
        f"/api/v1/visits/{unverified}/reason/", {"reason_code": "no_location_fix", "note": "Forêt"},
        format="json",
    ).json()
    assert body["field_reason_code"] == "no_location_fix"
    assert body["state"] == "unverified"  # a reason is not a resolution


def test_invariant_missed_requires_resolver_at_database_level(ft, worksite, check_in):
    from django.db import IntegrityError, transaction

    visit = Visit.objects.get(pk=check_in(ft, worksite, accuracy_m=500).json()["id"])
    visit.state, visit.unverified_reason = "missed", None
    with pytest.raises(IntegrityError), transaction.atomic():
        visit.save()
