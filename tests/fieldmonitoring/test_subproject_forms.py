"""Sub-project forms (COSO spec, 7 Oct 2026): identification creates the worksite, and the
lifecycle opens inspection → provisional handover → post-handover follow-up.

The forms come from the real seed command, so these tests also check its schemas.
"""
import uuid

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import Client

from administrativelevels.models import RURAL, URBAN
from fieldmonitoring.registry.models import DecisionStatus, ProvisionalCoordinate, Worksite
from trackableobjects import lifecycle, visibility
from trackableobjects.management.commands.seed_demo_forms import DEMO_GROUP
from trackableobjects.management.commands import seed_suivi_chantier as spec
from trackableobjects.models import (
    FollowUpEvent,
    FollowUpEventResponse,
    RecordStageChange,
    TrackableObject,
    TrackableObjectInstance,
)

from .conftest import BASE_LAT, BASE_LNG

pytestmark = pytest.mark.django_db

SYNC, PUSH = "/api/v1/forms/sync/", "/api/v1/forms/push/"
PHOTO = "Attachment"


@pytest.fixture
def forms(levels):
    call_command("seed_suivi_chantier", stdout=open("/dev/null", "w"))
    return {
        "record": TrackableObject.objects.get(name=spec.RECORD),
        "f2": FollowUpEvent.objects.get(name=spec.F2),
        "f3": FollowUpEvent.objects.get(name=spec.F3),
        "f4": FollowUpEvent.objects.get(name=spec.F4),
    }


@pytest.fixture
def agent(fc):
    fc.groups.add(Group.objects.get(name=DEMO_GROUP))
    return fc


def push(client_for, user, *items):
    r = client_for(user).post(PUSH, {"items": list(items)}, format="json")
    assert r.status_code == 200, r.content
    return r.json()["results"]


def identification(village, **overrides):
    answers = {
        "nom": "Forage de Séguéla",
        "financement": "FA1",
        "secteur": "Eau et assainissement",
        "sous_secteur_s03": "Eau potable",
        "village": village.pk,
        "site_physique": True,
        "position": f"{BASE_LAT:.6f} {BASE_LNG:.6f} 8.00",
        "maitrise_ouvrage": "MOC",
        "entreprise": "BTP Sud",
        "montant": 25_000_000,
        "date_demarrage": "2026-09-01",
        "date_fin_prevue": "2027-03-01",
        "photo_initiale_1": PHOTO,
        "photo_initiale_2": PHOTO,
    }
    answers.update(overrides)
    return answers


def inspection(**overrides):
    answers = {
        "phase": "Gros œuvre",
        "taux_physique": 40,
        "taux_financier": 30,
        "entreprise_presente": False,
        "responsable_hse": True,
        "pharmacie": True,
        "signalisation": False,
        "travaux_hauteur": False,
        "dechets": "Satisfaisante",
        "incident": False,
        "autre_probleme": False,
        "retard": False,
        "photo_1": PHOTO,
        "photo_2": PHOTO,
    }
    answers.update(overrides)
    return answers


def handover(decision, **overrides):
    answers = {
        "date_reception": "2026-10-01",
        "parties": ["Commune", "Entreprise"],
        "decision": decision,
        "photo_1": PHOTO,
        "photo_2": PHOTO,
    }
    if decision == spec.WITH_RESERVES:
        answers.update(reserves="Peinture à reprendre", delai_reserves=30)
    if decision == spec.POSTPONED:
        answers.update(motif_ajournement="Fuite au réservoir", date_nouvelle_reception="2026-11-01")
    else:
        answers["proces_verbal"] = PHOTO
    answers.update(overrides)
    return answers


def post_handover():
    return {
        "etat": "Fonctionnel", "degradations": False, "comite": True, "comite_fonctionnel": True,
        "entretien": False, "usagers": 300, "photo_1": PHOTO, "photo_2": PHOTO,
    }


def new_record(forms, answers):
    return {"kind": "record", "op": "create", "client_uuid": str(uuid.uuid4()),
            "trackable_object_id": forms["record"].pk, "answers": answers}


def new_response(event, record_id, answers):
    return {"kind": "response", "op": "create", "client_uuid": str(uuid.uuid4()),
            "follow_up_event_id": event.pk, "record_id": record_id, "answers": answers}


@pytest.fixture
def subproject(forms, agent, village, client_for):
    [result] = push(client_for, agent, new_record(forms, identification(village)))
    assert result["status"] == "created", result
    return TrackableObjectInstance.objects.get(pk=result["id"])


def answer(client_for, agent, event, record, answers):
    [result] = push(client_for, agent, new_response(event, record.pk, answers))
    assert result["status"] == "created", result
    record.refresh_from_db()
    return result


# --- the seed command -----------------------------------------------------------------------


def test_seed_creates_the_four_forms_and_is_idempotent(forms):
    record = forms["record"]
    assert record.creates_worksite and lifecycle.stage_keys(record)[0] == "works"
    assert set(record.follow_up_events.values_list("name", flat=True)) == {spec.F2, spec.F3, spec.F4}
    versions = {e.pk: e.schema_version for e in FollowUpEvent.objects.all()}
    call_command("seed_suivi_chantier", stdout=open("/dev/null", "w"))
    assert TrackableObject.objects.filter(name=spec.RECORD).count() == 1
    assert {e.pk: e.schema_version for e in FollowUpEvent.objects.all()} == versions


def test_seed_lists_all_37_subsectors():
    assert sum(len(v) for v in spec.SECTORS.values()) == 37 and len(spec.SECTORS) == 8


# --- F1 identification -----------------------------------------------------------------------


def test_identification_creates_worksite_with_coordinates_pending(subproject, agent, village, config):
    assert subproject.stage == "works"
    worksite = Worksite.objects.get(trackable_object_instance=subproject)
    assert worksite.name == "Forage de Séguéla" and worksite.village == village
    # No geofence until a supervisor confirms the position: check-ins are unverified, never missed.
    assert worksite.location is None and worksite.is_provisional
    capture = ProvisionalCoordinate.objects.get(worksite=worksite)
    assert capture.status == DecisionStatus.PENDING and capture.captured_by == agent and capture.accuracy_m == 8
    assert abs(capture.location.y - BASE_LAT) < 1e-6
    assert worksite.assignments.filter(user=agent).exists()
    assert list(subproject.administrative_units.all()) == [village]
    assert worksite.tolerance_m == config.default_tolerance_m  # village zone unknown


@pytest.mark.parametrize("zone, radius", [(URBAN, 50), (RURAL, 100)])
def test_worksite_radius_follows_village_zone(forms, agent, village, client_for, zone, radius):
    village.zone = zone
    village.save()
    push(client_for, agent, new_record(forms, identification(village)))
    assert Worksite.objects.get(village=village).tolerance_m == radius


def test_subsector_is_required_only_for_the_chosen_sector(forms, agent, village, client_for):
    missing = identification(village)
    del missing["sous_secteur_s03"]
    [result] = push(client_for, agent, new_record(forms, missing))
    assert result["status"] == "invalid" and "sous_secteur_s03" in result["errors"]
    [ok] = push(client_for, agent, new_record(forms, identification(village, sous_secteur_s01="Mares")))
    assert ok["status"] == "created"
    assert "sous_secteur_s01" not in TrackableObjectInstance.objects.get(pk=ok["id"]).jsonForm


def test_no_physical_site_still_needs_a_position_but_not_the_contract(forms, agent, village, client_for):
    answers = identification(village, site_physique=False)
    for name in ("entreprise", "montant", "date_demarrage", "date_fin_prevue", "photo_initiale_1", "photo_initiale_2"):
        del answers[name]
    [ok] = push(client_for, agent, new_record(forms, answers))
    assert ok["status"] == "created"
    del answers["position"]
    [result] = push(client_for, agent, new_record(forms, answers))
    assert result["status"] == "invalid" and "position" in result["errors"]


def test_editing_the_name_renames_the_worksite(subproject, agent, client_for, village):
    item = {"kind": "record", "op": "update", "id": subproject.pk, "base_version": subproject.version,
            "answers": identification(village, nom="Forage de Séguéla Nord")}
    [result] = push(client_for, agent, item)
    assert result["status"] == "updated"
    assert Worksite.objects.get(trackable_object_instance=subproject).name == "Forage de Séguéla Nord"
    assert Worksite.objects.count() == 1


# --- lifecycle -------------------------------------------------------------------------------


def test_full_lifecycle_works_acceptance_postponed_accepted(subproject, forms, agent, client_for):
    answer(client_for, agent, forms["f2"], subproject, inspection())
    assert subproject.stage == "works"
    answer(client_for, agent, forms["f2"], subproject, inspection(phase=spec.DONE))
    assert subproject.stage == "acceptance"
    answer(client_for, agent, forms["f3"], subproject, handover(spec.POSTPONED))
    assert subproject.stage == "postponed"
    answer(client_for, agent, forms["f3"], subproject, handover(spec.WITH_RESERVES))
    assert subproject.stage == "accepted"
    answer(client_for, agent, forms["f4"], subproject, post_handover())
    assert subproject.stage == "accepted"
    moves = [(c.from_stage, c.to_stage) for c in RecordStageChange.objects.order_by("id")]
    assert moves == [("works", "acceptance"), ("acceptance", "postponed"), ("postponed", "accepted")]


def test_handover_requires_minutes_unless_postponed(subproject, forms, agent, client_for):
    lifecycle._move(subproject, "acceptance")
    no_minutes = handover(spec.WITHOUT_RESERVES)
    del no_minutes["proces_verbal"]
    [result] = push(client_for, agent, new_response(forms["f3"], subproject.pk, no_minutes))
    assert result["status"] == "invalid" and "proces_verbal" in result["errors"]


def test_definitive_stop_terminates_and_supervisor_reopens(subproject, forms, agent, client_for, sc):
    stop = inspection(phase=spec.STOPPED, arret_date="2026-10-01", arret_nature=spec.DEFINITIVE,
                      arret_raisons=["Litige foncier"])
    answer(client_for, agent, forms["f2"], subproject, stop)
    assert subproject.stage == "terminated"
    assert list(visibility.available_follow_up_events(agent, subproject)) == []
    assert lifecycle.reopen(subproject, sc, note="Résiliation annulée") == "works"
    change = subproject.stage_changes.first()
    assert (change.from_stage, change.to_stage, change.changed_by, change.note) == (
        "terminated", "works", sc, "Résiliation annulée"
    )


def test_temporary_stop_asks_for_restart_date_and_stays_in_works(subproject, forms, agent, client_for):
    stop = inspection(phase=spec.STOPPED, arret_date="2026-10-01", arret_nature=spec.TEMPORARY,
                      arret_raisons=["Autre"])
    [result] = push(client_for, agent, new_response(forms["f2"], subproject.pk, stop))
    assert result["status"] == "invalid" and {"arret_raison_autre", "reprise_date"} <= set(result["errors"])
    answer(client_for, agent, forms["f2"], subproject,
           {**stop, "arret_raison_autre": "Fête locale", "reprise_date": "2099-01-01"})
    assert subproject.stage == "works"


def test_late_offline_answer_is_kept_but_moves_nothing(subproject, forms, agent, client_for):
    lifecycle._move(subproject, "accepted")
    # An inspection saying "works finished", filled offline before the handover, arrives now.
    result = answer(client_for, agent, forms["f2"], subproject, inspection(phase=spec.DONE))
    assert FollowUpEventResponse.objects.filter(pk=result["id"]).exists()
    assert subproject.stage == "accepted"


def test_available_events_follow_the_stage(subproject, forms, agent):
    def names():
        return {e.name for e in visibility.available_follow_up_events(agent, subproject)}

    assert names() == {spec.F2}
    lifecycle._move(subproject, "acceptance")
    assert names() == {spec.F2, spec.F3}
    lifecycle._move(subproject, "postponed")
    assert names() == {spec.F2, spec.F3}
    lifecycle._move(subproject, "accepted")
    assert names() == {spec.F4}


def test_record_types_without_stages_are_unchanged(fc):
    plain = TrackableObject.objects.create(name="Plain", description="", jsonForm={})
    record = TrackableObjectInstance.objects.create(trackable_object=plain, jsonForm={})
    lifecycle.on_record_created(record, fc)
    assert record.stage == "" and lifecycle.is_open(FollowUpEvent(stages=["works"]), record)


def test_sync_sends_stages_rules_and_record_stage(subproject, forms, agent, client_for):
    body = client_for(agent).get(SYNC).json()
    [record_type] = [t for t in body["trackable_objects"] if t["id"] == forms["record"].pk]
    assert record_type["stages"][0] == {"key": "works", "label": "Travaux en cours"}
    assert record_type["creates_worksite"] is True
    f3 = next(e for e in body["follow_up_events"] if e["id"] == forms["f3"].pk)
    assert f3["stages"] == ["acceptance", "postponed"] and f3["stage_rules"][0]["to"] == "accepted"
    [record] = [r for r in body["records"] if r["id"] == subproject.pk]
    assert record["stage"] == "works"


# --- MIS: reopen ------------------------------------------------------------------------------


def test_mis_staff_reopen_needs_a_reason(subproject, staff_user):
    lifecycle._move(subproject, "terminated")
    client = Client()
    client.force_login(staff_user)
    url = f"/en/trackable-objects/response/{subproject.pk}/reopen/"
    detail = client.get(f"/en/trackable-objects/response/{subproject.pk}/")
    assert detail.status_code == 200 and "Terminé (résilié)" in detail.content.decode()
    client.post(url, {"note": ""})
    subproject.refresh_from_db()
    assert subproject.stage == "terminated"
    client.post(url, {"note": "Erreur de saisie"})
    subproject.refresh_from_db()
    assert subproject.stage == "works"


# --- coordinates: the communal supervisor confirms -------------------------------------------


def test_sc_confirms_coordinates_of_their_team_only(subproject, sc, other_sc, client_for):
    worksite = Worksite.objects.get(trackable_object_instance=subproject)
    capture = worksite.provisional_coordinates.get()
    assert client_for(other_sc).get("/api/v1/coordinates/pending/").json()["count"] == 0
    assert client_for(other_sc).post(f"/api/v1/coordinates/{capture.pk}/confirm/").status_code == 404
    assert client_for(sc).get("/api/v1/coordinates/pending/").json()["count"] == 1
    assert client_for(sc).post(f"/api/v1/coordinates/{capture.pk}/confirm/").status_code == 200
    worksite.refresh_from_db()
    assert worksite.location is not None and not worksite.is_provisional


# --- village zones ----------------------------------------------------------------------------


def test_import_village_zones_sets_zone_and_worksite_radius(tmp_path, village, worksite):
    sheet = tmp_path / "zones.csv"
    sheet.write_text("Village;Zone\nSéguéla;Urbaine\nNulle part;Rurale\n", encoding="utf-8")
    call_command("import_village_zones", str(sheet), "--update-worksites", stdout=open("/dev/null", "w"))
    village.refresh_from_db()
    worksite.refresh_from_db()
    assert village.zone == URBAN and worksite.tolerance_m == 50


def test_import_village_zones_dry_run_writes_nothing(tmp_path, village):
    sheet = tmp_path / "zones.csv"
    sheet.write_text("Village,Zone\nSeguela,rural\n", encoding="utf-8")
    call_command("import_village_zones", str(sheet), "--dry-run", stdout=open("/dev/null", "w"))
    village.refresh_from_db()
    assert village.zone == ""

