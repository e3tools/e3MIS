"""Forms API for the field app: sync, push (offline replays), attachments."""
import copy
import uuid
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from administrativelevels.models import AdministrativeUnit
from subprojects.models import Attachment
from trackableobjects.models import (
    FollowUpEvent,
    FollowUpEventDependency,
    FollowUpEventResponse,
    FollowUpEventTrackableObject,
    TrackableObject,
    TrackableObjectInstance,
)

from .conftest import SCHEMA

pytestmark = pytest.mark.django_db

SYNC, PUSH, FILES = "/api/v1/forms/sync/", "/api/v1/forms/push/", "/api/v1/forms/attachments/"


def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def push(user, *items):
    r = api(user).post(PUSH, {"items": list(items)}, format="json")
    assert r.status_code == 200, r.content
    return r.json()["results"]


def new_record(to, answers=None, key=None):
    return {"kind": "record", "op": "create", "client_uuid": key or str(uuid.uuid4()),
            "trackable_object_id": to.pk, "answers": answers or {"name": "Puits 1", "ok": True}}


# --- access ------------------------------------------------------------------------------------


def test_anonymous_is_401_and_desktop_users_are_refused(staff_user):
    assert APIClient().get(SYNC).status_code == 401
    assert api(staff_user).get(SYNC).status_code == 403


# --- sync --------------------------------------------------------------------------------------


def test_full_sync_has_templates_events_records_and_units(agent, trackable_object, follow_up_event, instance, response, unit):
    body = api(agent).get(SYNC).json()
    assert body["full"] is True
    [to] = body["trackable_objects"]
    assert to["id"] == trackable_object.pk and to["can_create"] and to["schema"] == SCHEMA
    [event] = body["follow_up_events"]
    assert event["trackable_object_ids"] == [trackable_object.pk] and not event["standalone"]
    assert body["record_ids"] == [instance.pk] and body["records"][0]["answers"]["name"] == "École A"
    assert body["records"][0]["created_by_me"] is True
    assert body["response_ids"] == [response.pk]
    assert {u["id"] for u in body["administrative_units"]} == {unit.pk}


def test_delta_sync_returns_only_changes_but_all_ids(agent, instance, response):
    since = (timezone.now() + timedelta(seconds=1)).isoformat()
    body = api(agent).get(SYNC, {"since": since}).json()
    assert body["full"] is False and body["records"] == [] and body["record_ids"] == [instance.pk]


def test_bad_since_is_400(agent):
    assert api(agent).get(SYNC, {"since": "yesterday"}).status_code == 400


def test_agent_without_shared_groups_sees_nothing(other_agent, trackable_object, instance):
    body = api(other_agent).get(SYNC).json()
    assert body["trackable_objects"] == [] and body["record_ids"] == []


def test_listed_but_not_fillable_when_missing_one_of_the_groups(agent, trackable_object):
    trackable_object.groups.add(Group.objects.create(name="Autre"))
    [to] = api(agent).get(SYNC).json()["trackable_objects"]
    assert to["can_create"] is False


def test_records_follow_administrative_units(agent, other_agent, trackable_object, unit):
    elsewhere = AdministrativeUnit.objects.create(name="Parakou", level=unit.level)
    theirs = TrackableObjectInstance.objects.create(trackable_object=trackable_object, created_by=other_agent, jsonForm={"name": "x"})
    theirs.administrative_units.add(elsewhere)
    open_to_all = TrackableObjectInstance.objects.create(
        trackable_object=trackable_object, created_by=other_agent, jsonForm={"name": "y"}, restrict_by_administrative_units=False
    )
    here = TrackableObjectInstance.objects.create(trackable_object=trackable_object, created_by=other_agent, jsonForm={"name": "z"})
    here.administrative_units.add(unit)
    assert set(api(agent).get(SYNC).json()["record_ids"]) == {open_to_all.pk, here.pk}


# --- push: records -----------------------------------------------------------------------------


def test_create_record_then_replay_is_a_duplicate(agent, trackable_object):
    item = new_record(trackable_object)
    [first] = push(agent, item)
    assert first["status"] == "created" and first["version"] == 1
    created = TrackableObjectInstance.objects.get(pk=first["id"])
    assert created.jsonForm == {"name": "Puits 1", "ok": True} and created.created_by == agent
    assert created.schema_version == trackable_object.schema_version
    [again] = push(agent, item)
    assert again["status"] == "duplicate" and again["id"] == first["id"]
    assert TrackableObjectInstance.objects.count() == 1


def test_invalid_answers_are_rejected_per_field(agent, trackable_object):
    [result] = push(agent, new_record(trackable_object, {"ok": True}))
    assert result["status"] == "invalid" and "name" in result["errors"]


def test_unknown_answer_keys_are_dropped(agent, trackable_object):
    [result] = push(agent, new_record(trackable_object, {"name": "A", "hack": "x"}))
    assert "hack" not in TrackableObjectInstance.objects.get(pk=result["id"]).jsonForm


def test_one_bad_item_does_not_stop_the_batch(agent, trackable_object):
    results = push(agent, new_record(trackable_object, {"ok": True}), new_record(trackable_object))
    assert [r["status"] for r in results] == ["invalid", "created"]


def test_cannot_create_without_all_groups(agent, trackable_object):
    trackable_object.groups.add(Group.objects.create(name="Autre"))
    assert push(agent, new_record(trackable_object))[0]["status"] == "forbidden"


def test_update_with_current_version(agent, instance):
    item = {"kind": "record", "op": "update", "id": instance.pk, "base_version": 1, "answers": {"name": "École A2"}}
    [result] = push(agent, item)
    assert result["status"] == "updated" and result["version"] == 2
    # The same update replayed (response lost on the way back) is recognised.
    assert push(agent, item)[0]["status"] == "duplicate"


def test_stale_update_is_a_conflict_with_the_server_copy(agent, instance):
    TrackableObjectInstance.objects.filter(pk=instance.pk).update(version=3, jsonForm={"name": "par le bureau"})
    [result] = push(agent, {"kind": "record", "op": "update", "id": instance.pk, "base_version": 1, "answers": {"name": "moi"}})
    assert result["status"] == "conflict" and result["reason"] == "stale"
    assert result["server"]["answers"] == {"name": "par le bureau"}
    assert TrackableObjectInstance.objects.get(pk=instance.pk).jsonForm == {"name": "par le bureau"}


def test_cannot_update_a_record_out_of_sight(other_agent, instance):
    other_agent.groups.add(*instance.trackable_object.groups.all())
    result = push(other_agent, {"kind": "record", "op": "update", "id": instance.pk, "base_version": 1, "answers": {"name": "x"}})
    assert result[0]["status"] == "forbidden"


# --- push: responses ---------------------------------------------------------------------------


def test_record_and_follow_up_created_offline_in_one_batch(agent, trackable_object, follow_up_event):
    key = str(uuid.uuid4())
    results = push(
        agent,
        new_record(trackable_object, key=key),
        {"kind": "response", "op": "create", "client_uuid": str(uuid.uuid4()), "follow_up_event_id": follow_up_event.pk,
         "record_client_uuid": key, "answers": {"name": "visite"}},
    )
    assert [r["status"] for r in results] == ["created", "created"]
    assert FollowUpEventResponse.objects.get(pk=results[1]["id"]).trackable_object_instance_id == results[0]["id"]


def test_one_off_event_answered_twice_is_a_conflict(agent, follow_up_event, instance, response):
    FollowUpEvent.objects.filter(pk=follow_up_event.pk).update(is_one_off=True)
    [result] = push(agent, {"kind": "response", "op": "create", "client_uuid": str(uuid.uuid4()),
                            "follow_up_event_id": follow_up_event.pk, "record_id": instance.pk, "answers": {"name": "2"}})
    assert result["status"] == "conflict" and result["reason"] == "already_answered"
    assert result["server"]["id"] == response.pk


def test_dependencies_must_be_answered_first(agent, trackable_object, follow_up_event, instance, tf_group):
    child = FollowUpEvent.objects.create(name="Réception", jsonForm=SCHEMA)
    child.groups.add(tf_group)
    FollowUpEventTrackableObject.objects.create(follow_up_event=child, trackable_object=trackable_object)
    FollowUpEventDependency.objects.create(parent=follow_up_event, child=child)

    def answer(event):
        return {"kind": "response", "op": "create", "client_uuid": str(uuid.uuid4()),
                "follow_up_event_id": event.pk, "record_id": instance.pk, "answers": {"name": "ok"}}

    blocked = push(agent, answer(child))[0]
    assert blocked["status"] == "invalid" and blocked["depends_on"] == [follow_up_event.pk]
    assert [r["status"] for r in push(agent, answer(follow_up_event), answer(child))] == ["created", "created"]


def test_standalone_event_needs_no_record(agent, tf_group):
    event = FollowUpEvent.objects.create(name="Réunion", jsonForm=SCHEMA)
    event.groups.add(tf_group)
    body = api(agent).get(SYNC).json()
    assert [e["standalone"] for e in body["follow_up_events"]] == [True]
    [result] = push(agent, {"kind": "response", "op": "create", "client_uuid": str(uuid.uuid4()),
                            "follow_up_event_id": event.pk, "answers": {"name": "réunion"}})
    assert result["status"] == "created"
    assert api(agent).get(SYNC).json()["response_ids"] == [result["id"]]


def test_event_for_another_object_type_is_refused(agent, follow_up_event, staff_user, tf_group):
    other_type = TrackableObject.objects.create(name="Pont", jsonForm=SCHEMA, created_by=staff_user)
    other_type.groups.add(tf_group)
    record = push(agent, new_record(other_type))[0]
    [result] = push(agent, {"kind": "response", "op": "create", "client_uuid": str(uuid.uuid4()),
                            "follow_up_event_id": follow_up_event.pk, "record_id": record["id"], "answers": {"name": "x"}})
    assert result["status"] == "invalid"


# --- validation details ------------------------------------------------------------------------


def with_fields(to, **properties_and_options):
    schema = copy.deepcopy(SCHEMA)
    for name, (prop, options, required) in properties_and_options.items():
        schema["form"][0]["page"]["properties"][name] = prop
        schema["form"][0]["options"]["fields"][name] = options
        if required:
            schema["form"][0]["page"]["required"].append(name)
    to.jsonForm = schema
    to.save()


def test_field_hidden_by_a_condition_is_not_required(agent, trackable_object):
    with_fields(trackable_object, reason=(
        {"type": "string"},
        {"label": "Why", "dependencies": {"conditions": [{"field": "ok", "operator": "equals", "value": "False"}]}},
        True,
    ))
    shown_and_missing = push(agent, new_record(trackable_object, {"name": "A", "ok": False}))[0]
    assert shown_and_missing["status"] == "invalid" and "reason" in shown_and_missing["errors"]
    hidden = push(agent, new_record(trackable_object, {"name": "A", "ok": True, "reason": "ignored"}))[0]
    assert hidden["status"] == "created"
    assert "reason" not in TrackableObjectInstance.objects.get(pk=hidden["id"]).jsonForm


def test_required_file_needs_the_marker_then_the_upload(agent, other_agent, trackable_object):
    with_fields(trackable_object, photo=({"type": "file"}, {"label": "Photo"}, True))
    assert push(agent, new_record(trackable_object, {"name": "A"}))[0]["status"] == "invalid"
    [record] = push(agent, new_record(trackable_object, {"name": "A", "photo": "Attachment"}))
    assert record["status"] == "created"

    key = str(uuid.uuid4())
    payload = {"client_uuid": key, "kind": "record", "owner_id": record["id"], "field_name": "photo",
               "file": SimpleUploadedFile("p.jpg", b"jpeg-bytes", content_type="image/jpeg")}
    r = api(agent).post(FILES, payload, format="multipart")
    assert r.status_code == 201 and r.json()["status"] == "created"
    payload["file"] = SimpleUploadedFile("p.jpg", b"jpeg-bytes", content_type="image/jpeg")
    assert api(agent).post(FILES, payload, format="multipart").json()["status"] == "duplicate"
    assert Attachment.objects.count() == 1

    url = r.json()["url"]
    assert api(agent).get(url).status_code == 200
    assert api(other_agent).get(url).status_code == 403
    [synced] = api(agent).get(SYNC).json()["records"]
    assert synced["attachments"][0]["field_name"] == "photo"


def test_upload_for_a_field_without_the_marker_is_refused(agent, instance):
    r = api(agent).post(FILES, {"client_uuid": str(uuid.uuid4()), "kind": "record", "owner_id": instance.pk,
                                "field_name": "name", "file": SimpleUploadedFile("x.txt", b"x")}, format="multipart")
    assert r.status_code == 400


def test_upload_before_the_record_is_pushed_is_404(agent):
    r = api(agent).post(FILES, {"client_uuid": str(uuid.uuid4()), "kind": "record", "owner_client_uuid": str(uuid.uuid4()),
                                "field_name": "photo", "file": SimpleUploadedFile("x.jpg", b"x")}, format="multipart")
    assert r.status_code == 404


def test_demo_forms_work_end_to_end(agent):
    from django.core.management import call_command

    call_command("seed_demo_forms")
    call_command("seed_demo_forms")  # idempotent
    agent.groups.add(Group.objects.get(name="Community facilitator"))
    body = api(agent).get(SYNC).json()
    water = next(t for t in body["trackable_objects"] if t["name"] == "Point d'eau")
    events = {e["name"]: e for e in body["follow_up_events"]}
    assert water["can_create"] and events["Réunion communautaire"]["standalone"]
    assert events["Réception des travaux"]["depends_on"] == [events["Inspection du point d'eau"]["id"]]

    key = str(uuid.uuid4())
    results = push(
        agent,
        {"kind": "record", "op": "create", "client_uuid": key, "trackable_object_id": water["id"],
         "answers": {"nom": "Forage Godomey", "type": "Forage", "fonctionnel": False, "menages": 120,
                     "position": "6.41,2.34,12", "photo": "Attachment"}},
        {"kind": "response", "op": "create", "client_uuid": str(uuid.uuid4()), "record_client_uuid": key,
         "follow_up_event_id": events["Inspection du point d'eau"]["id"],
         "answers": {"etat": "Mauvais", "reparation": True, "date": "2026-09-01"}},
    )
    assert results[0]["status"] == "created"
    # The repair details become required once "repair needed" is yes.
    assert results[1]["status"] == "invalid" and "details" in results[1]["errors"]
    record = TrackableObjectInstance.objects.get(pk=results[0]["id"])
    assert record.jsonForm["fonctionnel"] is False and record.identifier == "Forage Godomey"
