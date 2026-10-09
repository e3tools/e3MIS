"""Forms filled during a worksite visit (Brice, 8 Oct 2026): each form is linked to the visit and
its check-in, and a check-out without a form goes to a person, never to "missed"."""
import uuid

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command

from fieldmonitoring.registry.models import Worksite, WorksiteAssignment
from fieldmonitoring.visits.models import UnverifiedReason, Visit, VisitState
from trackableobjects.management.commands import seed_suivi_chantier as spec
from trackableobjects.management.commands.seed_demo_forms import DEMO_GROUP
from trackableobjects.models import FollowUpEvent, FollowUpEventResponse, TrackableObject, TrackableObjectInstance

from .test_subproject_forms import identification, inspection

pytestmark = pytest.mark.django_db

PUSH = "/api/v1/forms/push/"


@pytest.fixture
def forms(levels):
    call_command("seed_suivi_chantier", stdout=open("/dev/null", "w"))
    return {"record": TrackableObject.objects.get(name=spec.RECORD), "f2": FollowUpEvent.objects.get(name=spec.F2)}


@pytest.fixture
def agent(ft):
    ft.groups.add(Group.objects.get_or_create(name=DEMO_GROUP)[0])
    return ft


def push(client_for, user, item):
    r = client_for(user).post(PUSH, {"items": [item]}, format="json")
    assert r.status_code == 200, r.content
    [result] = r.json()["results"]
    return result


def record_item(forms, answers, **extra):
    return {"kind": "record", "op": "create", "client_uuid": str(uuid.uuid4()),
            "trackable_object_id": forms["record"].pk, "answers": answers, **extra}


def response_item(event, record_id, answers, **extra):
    return {"kind": "response", "op": "create", "client_uuid": str(uuid.uuid4()),
            "follow_up_event_id": event.pk, "record_id": record_id, "answers": answers, **extra}


@pytest.fixture
def subproject(forms, agent, village, client_for):
    result = push(client_for, agent, record_item(forms, identification(village)))
    instance = TrackableObjectInstance.objects.get(pk=result["id"])
    return instance


def visit_at(check_in, user, worksite):
    key = str(uuid.uuid4())
    response = check_in(user, worksite, idempotency_key=key)
    assert response.status_code == 201, response.content
    return Visit.objects.get(pk=response.json()["id"]), key


def test_inspection_saved_during_a_visit_is_linked_to_it(subproject, forms, agent, check_in, client_for):
    site = Worksite.objects.get(trackable_object_instance=subproject)
    visit, key = visit_at(check_in, agent, site)
    result = push(client_for, agent, response_item(forms["f2"], subproject.pk, inspection(), visit_key=key))
    response = FollowUpEventResponse.objects.get(pk=result["id"])
    assert response.visit == visit and response.visit_key == key
    body = client_for(agent).get(f"/api/v1/visits/{visit.pk}/").json()
    # Form 1, filled the same day just before this first visit, belongs to it too.
    assert body["forms"] == [
        {"kind": "record", "id": subproject.pk, "name": spec.RECORD, "label": "Forage de Séguéla"},
        {"kind": "response", "id": response.pk, "name": spec.F2, "label": spec.F2},
    ]


def test_form_arriving_before_its_visit_is_linked_at_check_in(subproject, forms, agent, check_in, client_for):
    site = Worksite.objects.get(trackable_object_instance=subproject)
    key = str(uuid.uuid4())
    result = push(client_for, agent, response_item(forms["f2"], subproject.pk, inspection(), visit_key=key))
    assert FollowUpEventResponse.objects.get(pk=result["id"]).visit is None
    check_in(agent, site, idempotency_key=key)
    assert FollowUpEventResponse.objects.get(pk=result["id"]).visit.checkin_idempotency_key == key


def test_identification_at_a_site_added_from_the_field_completes_it(forms, agent, village, check_in, client_for):
    # "Not listed — add a worksite", check-in there, then form 1 during that visit.
    site = Worksite.objects.create(name="Nouveau site", village=village, is_provisional=True, created_by=agent)
    WorksiteAssignment.objects.create(user=agent, worksite=site, assigned_on=site.created_at.date())
    visit, key = visit_at(check_in, agent, site)
    result = push(client_for, agent, record_item(forms, identification(village), visit_key=key, worksite_id=str(site.pk)))
    assert result["status"] == "created", result
    site.refresh_from_db()
    record = TrackableObjectInstance.objects.get(pk=result["id"])
    assert list(Worksite.objects.filter(trackable_object_instance=record)) == [site]  # no second site
    assert site.trackable_object_instance == record and site.name == "Forage de Séguéla"
    assert record.visit == visit
    assert site.provisional_coordinates.filter(visit=visit).count() == 2  # check-in capture + form 1


def test_identification_cannot_take_over_someone_elses_site(forms, agent, village, client_for, fc):
    theirs = Worksite.objects.create(name="Site de Mariam", village=village, created_by=fc)
    result = push(client_for, agent, record_item(forms, identification(village), worksite_id=str(theirs.pk)))
    theirs.refresh_from_db()
    assert theirs.trackable_object_instance is None  # not the agent's: a new site is created instead
    assert Worksite.objects.filter(trackable_object_instance_id=result["id"]).exists()


def test_check_out_without_a_form_goes_to_review_with_the_agents_note(subproject, agent, check_in, client_for):
    site = Worksite.objects.get(trackable_object_instance=subproject)
    site.location = site.provisional_coordinates.get().location  # confirmed by the supervisor
    site.save()
    visit, _ = visit_at(check_in, agent, site)
    body = client_for(agent).post(
        f"/api/v1/visits/{visit.pk}/check-out/",
        {"idempotency_key": "out-1", "form_missing_note": "Pluie, téléphone mouillé"}, format="json",
    ).json()
    assert body["state"] == VisitState.UNVERIFIED and body["unverified_reason"] == UnverifiedReason.FORM_MISSING
    # The note is the field reason: the app does not ask again, the reviewer sees it.
    assert body["field_reason"] == "Pluie, téléphone mouillé" and body["needs_reason"] is False


def test_check_out_from_old_builds_is_unchanged(ft, worksite, check_in, client_for):
    visit, _ = visit_at(check_in, ft, worksite)
    body = client_for(ft).post(f"/api/v1/visits/{visit.pk}/check-out/", {"idempotency_key": "out-1"}, format="json").json()
    assert body["state"] == VisitState.VERIFIED and body["forms"] == []


def test_worksites_tell_the_app_which_record_describes_them(subproject, agent, client_for):
    sites = client_for(agent).get("/api/v1/me/worksites/").json()
    [site] = [s for s in sites if s["record_id"] is not None]
    assert site["record_id"] == subproject.pk
    assert site["record_client_uuid"] == str(subproject.client_uuid)


def test_mis_form_page_shows_the_check_in(subproject, forms, agent, check_in, client_for, staff_user):
    from django.test import Client

    site = Worksite.objects.get(trackable_object_instance=subproject)
    _, key = visit_at(check_in, agent, site)
    result = push(client_for, agent, response_item(forms["f2"], subproject.pk, inspection(), visit_key=key))
    client = Client()
    client.force_login(staff_user)
    page = client.get(f"/en/trackable-objects/follow-up-event/response/{result['id']}/").content.decode()
    assert "Forage de Séguéla" in page and "Check-in" in page



def test_new_subproject_alone_in_its_village_is_listed_nearby(forms, agent, commune, levels, client_for):
    # Field test 8 Oct: identified in form 1, no confirmed position, no other site in the village.
    from administrativelevels.models import AdministrativeUnit

    alone = AdministrativeUnit.objects.create(name="Kpota", level=levels["village"], parent=commune)
    answers = identification(alone, position="8.100000 -6.500000 10.00")
    result = push(client_for, agent, record_item(forms, answers))
    site = Worksite.objects.get(trackable_object_instance_id=result["id"])
    body = client_for(agent).get("/api/v1/worksites/nearby/", {"lat": 8.1001, "lng": -6.5, "radius_m": 500}).json()
    assert [w["id"] for w in body] == [str(site.pk)]
    assert body[0]["record_id"] == result["id"] and body[0]["has_coordinate"] is False
