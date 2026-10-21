"""Dashboard drill-downs: profiles, assigned worksites, visit history, worksite history."""

import pytest
import time_machine

from fieldmonitoring.visits.models import Visit
from tests.fieldmonitoring.conftest import utc

pytestmark = pytest.mark.django_db


@pytest.fixture
def visited(ft, worksite, check_in, client_for):
    with time_machine.travel(utc(2026, 9, 20, 9), tick=False):
        first = check_in(ft, worksite).json()["id"]
        client_for(ft).post(f"/api/v1/visits/{first}/check-out/", {"idempotency_key": "a"}, format="json")
    with time_machine.travel(utc(2026, 9, 25, 9), tick=False):
        second = check_in(ft, worksite, accuracy_m=500).json()["id"]
    return first, second


def test_profile_shows_person_presence_and_counts(sc, ft, visited, client_for):
    with time_machine.travel(utc(2026, 9, 28, 9), tick=False):
        body = client_for(sc).get(f"/api/v1/users/{ft.id}/profile/").json()
    assert body["user"]["full_name"] == ft.full_name and body["user"]["supervisor_id"] == str(sc.id)
    assert body["visits"]["total"] == 2 and body["visits"]["verified"] == 1
    assert body["visits"]["awaiting_review"] == 1
    assert body["presence"]["days_since"] == 8


def test_profile_is_scoped_to_the_sc_team(other_sc, ft, rdp, client_for):
    assert client_for(other_sc).get(f"/api/v1/users/{ft.id}/profile/").status_code == 403
    assert client_for(rdp).get(f"/api/v1/users/{ft.id}/profile/").status_code == 200


def test_field_users_cannot_open_profiles(ft, fc, client_for):
    assert client_for(fc).get(f"/api/v1/users/{ft.id}/profile/").status_code == 403


def test_assigned_worksites_with_the_persons_own_counts(sc, ft, worksite, unmapped_worksite, visited, client_for):
    from fieldmonitoring.registry.models import WorksiteAssignment

    WorksiteAssignment.objects.create(user=ft, worksite=unmapped_worksite, assigned_on="2026-01-01")
    with time_machine.travel(utc(2026, 9, 28, 9), tick=False):
        rows = client_for(sc).get(f"/api/v1/users/{ft.id}/worksites/").json()
    by_name = {r["name"]: r for r in rows}
    assert rows[0]["name"] == unmapped_worksite.name  # never visited first
    assert by_name[worksite.name]["visits"] == 2 and by_name[worksite.name]["verified"] == 1
    assert by_name[worksite.name]["days_since_last_verified"] == 8


def test_visit_history_newest_first_and_filterable_by_worksite(sc, ft, worksite, visited, client_for):
    body = client_for(sc).get(f"/api/v1/users/{ft.id}/visits/").json()
    assert body["count"] == 2
    assert [v["id"] for v in body["results"]] == [visited[1], visited[0]]
    assert body["results"][0]["has_photo"] is True
    other = client_for(sc).get(f"/api/v1/users/{ft.id}/visits/?worksite=00000000-0000-0000-0000-000000000000").json()
    assert other["count"] == 0


def test_worksite_detail_and_history(sc, ft, worksite, visited, client_for):
    with time_machine.travel(utc(2026, 9, 28, 9), tick=False):
        body = client_for(sc).get(f"/api/v1/worksites/{worksite.id}/").json()
    assert [a["full_name"] for a in body["assigned"]] == [ft.full_name]
    assert body["visits"]["total"] == 2 and body["visits"]["days_since_last_verified"] == 8
    history = client_for(sc).get(f"/api/v1/worksites/{worksite.id}/visits/").json()
    assert history["count"] == 2 and history["results"][0]["user"]["full_name"] == ft.full_name


def test_worksite_outside_the_sc_commune_is_hidden(other_sc, worksite, client_for):
    assert client_for(other_sc).get(f"/api/v1/worksites/{worksite.id}/").status_code == 404


def test_worksite_history_hides_other_teams_visits(sc, other_sc, worksite, rdp, check_in, client_for):
    from tests.fieldmonitoring.conftest import make_user

    outsider = make_user("nathalie", "fc", supervisor=other_sc, commune=other_sc.commune)
    from fieldmonitoring.registry.models import WorksiteAssignment

    WorksiteAssignment.objects.create(user=outsider, worksite=worksite, assigned_on="2026-01-01")
    check_in(outsider, worksite)
    assert client_for(sc).get(f"/api/v1/worksites/{worksite.id}/visits/").json()["count"] == 0
    assert client_for(rdp).get(f"/api/v1/worksites/{worksite.id}/visits/").json()["count"] == 1


def test_missing_photo_file_is_a_clean_404(sc, ft, visited, client_for):
    visit = Visit.objects.get(pk=visited[0])
    visit.photo.file.storage.delete(visit.photo.file.name)
    response = client_for(sc).get(f"/api/v1/visits/{visit.id}/photo/")
    assert response.status_code == 404 and response.json()["code"] == "photo_unavailable"


def test_field_user_sees_own_history_only(ft, fc, worksite, visited, client_for):
    mine = client_for(ft).get("/api/v1/me/visits/history/").json()
    assert mine["count"] == 2 and all(v["user"]["id"] == str(ft.id) for v in mine["results"])
    assert client_for(fc).get("/api/v1/me/visits/history/").json()["count"] == 0
    filtered = client_for(ft).get(f"/api/v1/me/visits/history/?worksite={worksite.id}&limit=1").json()
    assert filtered["count"] == 2 and len(filtered["results"]) == 1


def test_field_user_can_load_own_photo(ft, fc, visited, client_for):
    assert client_for(ft).get(f"/api/v1/visits/{visited[0]}/photo/").status_code == 200
    assert client_for(fc).get(f"/api/v1/visits/{visited[0]}/photo/").status_code == 403
