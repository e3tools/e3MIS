"""Epic 1 and Epic 6 registry stories: worksites, nearby, CSV import, high-risk, coordinates."""

import pytest
from django.contrib.gis.geos import Point

from administrativelevels.models import AdministrativeUnit
from fieldmonitoring.registry.importer import import_worksites
from fieldmonitoring.registry.models import Worksite
from tests.fieldmonitoring.conftest import BASE_LAT, BASE_LNG, north_of

pytestmark = pytest.mark.django_db


def test_story_1_3_null_coordinates_save_and_list(ft, unmapped_worksite, client_for):
    from fieldmonitoring.registry.models import WorksiteAssignment

    WorksiteAssignment.objects.create(user=ft, worksite=unmapped_worksite, assigned_on="2026-01-01")
    names = [w["name"] for w in client_for(ft).get("/api/v1/me/worksites/").json()]
    assert unmapped_worksite.name in names


def test_story_2_1_never_visited_sorts_first(ft, worksite, client_for):
    items = client_for(ft).get("/api/v1/me/worksites/").json()
    assert items[0]["days_since_last_visit"] is None


def test_story_1_3_completed_worksite_excluded(ft, worksite, client_for):
    worksite.status = "completed"
    worksite.save()
    assert client_for(ft).get("/api/v1/me/worksites/").json() == []


def test_story_1_3_csv_import(village, levels):
    # Units come from the MIS tree; the import only looks them up.
    AdministrativeUnit.objects.create(name="Bodokro", level=levels["village"], parent=village.parent)
    text = (
        "name,code,village,commune,region,latitude,longitude,tolerance_m,status\n"
        "Forage F-09,F-09,Séguéla,Dabou,Béré,7.96,-6.67,150,active\n"
        "Pont P-1,P-1,Bodokro,Dabou,Béré,,,,\n"
    )
    result = import_worksites(text)
    assert (result.created, result.errors) == (2, [])
    assert Worksite.objects.get(code="F-09").tolerance_m == 150
    assert Worksite.objects.get(code="P-1").location is None
    assert import_worksites(text).updated == 2


def test_story_1_3_csv_import_rolls_back_on_error():
    text = "name,village,commune,region,latitude,longitude\nA,V,C,R,7.9,\n"
    result = import_worksites(text)
    assert result.errors and Worksite.objects.count() == 0


def test_story_2_2_nearby_includes_unmapped_sites_in_same_village(regional, worksite, unmapped_worksite, client_for):
    lat, lng = north_of(BASE_LAT, BASE_LNG, 120)
    body = client_for(regional).get(f"/api/v1/worksites/nearby/?lat={lat}&lng={lng}").json()
    assert [w["name"] for w in body] == [worksite.name, unmapped_worksite.name]
    assert 110 <= body[0]["distance_m"] <= 130 and body[1]["distance_m"] is None


def test_story_2_2_nearby_excludes_far_sites(regional, village, client_for):
    lat, lng = north_of(BASE_LAT, BASE_LNG, 2000)
    Worksite.objects.create(name="Far", village=village, location=Point(lng, lat, srid=4326))
    assert client_for(regional).get(f"/api/v1/worksites/nearby/?lat={BASE_LAT}&lng={BASE_LNG}").json() == []


def test_story_2_2_not_listed_creates_provisional_worksite(regional, village, client_for):
    body = client_for(regional).post(
        "/api/v1/worksites/provisional/", {"name": "Nouveau puits", "village_id": str(village.id)}, format="json"
    ).json()
    assert body["is_provisional"] and not body["has_coordinate"]


def test_br15_high_risk_needs_rdp_approval(national, rdp, worksite, client_for):
    proposal = client_for(national).post(
        f"/api/v1/worksites/{worksite.id}/high-risk/",
        {"to_value": True, "reason": "Effondrement partiel signalé en août"}, format="json",
    ).json()
    worksite.refresh_from_db()
    assert not worksite.is_high_risk  # not effective until approved
    body = client_for(rdp).post(f"/api/v1/high-risk/{proposal['id']}/approve/").json()
    worksite.refresh_from_db()
    assert worksite.is_high_risk and body["review_due_on"] is not None


def test_br15_reason_is_mandatory_free_text(national, worksite, client_for):
    response = client_for(national).post(
        f"/api/v1/worksites/{worksite.id}/high-risk/", {"to_value": True, "reason": ""}, format="json"
    )
    assert response.status_code == 400


def test_br15_only_national_specialist_proposes(regional, worksite, client_for):
    response = client_for(regional).post(
        f"/api/v1/worksites/{worksite.id}/high-risk/", {"to_value": True, "reason": "Risque élevé"}, format="json"
    )
    assert response.status_code == 403


def test_story_6_4_confirming_coordinate_activates_location_check(sc, admin_user, unmapped_worksite, check_in, client_for):
    check_in(sc, unmapped_worksite)
    pending = client_for(admin_user).get("/api/v1/coordinates/pending/").json()
    assert pending["count"] == 1
    coord_id = pending["results"][0]["captures"][0]["id"]
    client_for(admin_user).post(f"/api/v1/coordinates/{coord_id}/confirm/")
    unmapped_worksite.refresh_from_db()
    assert unmapped_worksite.location is not None
    assert check_in(sc, unmapped_worksite).json()["state"] == "in_progress"


def test_photo_access_is_restricted(ft, other_sc, sc, worksite, check_in, client_for):
    visit_id = check_in(ft, worksite).json()["id"]
    assert client_for(sc).get(f"/api/v1/visits/{visit_id}/photo/").status_code == 200
    assert client_for(other_sc).get(f"/api/v1/visits/{visit_id}/photo/").status_code == 403


def test_unknown_decision_is_rejected(national, rdp, worksite, client_for):
    proposal = client_for(national).post(
        f"/api/v1/worksites/{worksite.id}/high-risk/", {"to_value": True, "reason": "Risque élevé ici"}, format="json"
    ).json()
    assert client_for(rdp).post(f"/api/v1/high-risk/{proposal['id']}/maybe/").status_code == 400


def test_worksite_list_shows_my_last_visit_and_todays_count(ft, worksite, check_in, client_for):
    import time_machine

    from tests.fieldmonitoring.conftest import utc

    with time_machine.travel(utc(2026, 9, 28, 9, 12), tick=False):
        check_in(ft, worksite, accuracy_m=500)
        row = client_for(ft).get("/api/v1/me/worksites/").json()[0]
    assert row["my_last_visit_state"] == "unverified"
    assert row["my_last_visit_at"].startswith("2026-09-28T09:12")
    assert row["my_visits_today"] == 1
    with time_machine.travel(utc(2026, 9, 29, 9, 0), tick=False):
        assert client_for(ft).get("/api/v1/me/worksites/").json()[0]["my_visits_today"] == 0
