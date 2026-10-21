"""Field agent flows on the mobile web screens: register a record, follow up, edit, visibility."""
import pytest
from django.urls import reverse

from trackableobjects.models import FollowUpEventResponse, TrackableObjectInstance

from .conftest import client_for

pytestmark = pytest.mark.django_db


def test_agent_registers_a_record(agent_client, agent, trackable_object):
    url = reverse("trackableobjects:mobile:trackable_object_create", kwargs={"pk": trackable_object.pk})
    assert agent_client.get(url).status_code == 200
    r = agent_client.post(url, {"name": "École B", "ok": "True"})
    assert r.status_code == 302
    created = TrackableObjectInstance.objects.get()
    assert created.jsonForm == {"name": "École B", "ok": True}
    assert created.created_by == agent


def test_required_field_is_enforced(agent_client, trackable_object):
    url = reverse("trackableobjects:mobile:trackable_object_create", kwargs={"pk": trackable_object.pk})
    r = agent_client.post(url, {"ok": "True"})
    assert r.status_code == 200  # form re-rendered with errors
    assert not TrackableObjectInstance.objects.exists()


def test_agent_outside_the_object_groups_is_refused(other_agent, trackable_object):
    url = reverse("trackableobjects:mobile:trackable_object_create", kwargs={"pk": trackable_object.pk})
    assert client_for(other_agent).get(url).status_code == 403


def test_agent_fills_a_follow_up(agent_client, agent, follow_up_event, instance):
    url = reverse(
        "trackableobjects:mobile:follow_up_event_response_create",
        kwargs={"trackable_instance": instance.pk, "follow_up_event": follow_up_event.pk},
    )
    assert agent_client.get(url).status_code == 200
    r = agent_client.post(url, {"name": "visit 1", "ok": "False"})
    assert r.status_code == 302
    resp = FollowUpEventResponse.objects.get()
    assert resp.trackable_object_instance == instance
    assert resp.jsonForm["name"] == "visit 1"


def test_agent_edits_a_record(agent_client, instance):
    url = reverse("trackableobjects:mobile:trackable_object_edit", kwargs={"pk": instance.pk})
    assert agent_client.get(url).status_code == 200
    r = agent_client.post(url, {"name": "École A2", "ok": "True"})
    assert r.status_code == 302
    instance.refresh_from_db()
    assert instance.jsonForm["name"] == "École A2"


def test_agent_reopens_a_follow_up(agent_client, response):
    url = reverse(
        "trackableobjects:mobile:follow_up_event_response_update",
        kwargs={"follow_up_event": response.follow_up_event_id, "response": response.pk},
    )
    assert agent_client.get(url).status_code == 200


def test_record_lists_render(agent_client, trackable_object, follow_up_event, instance):
    for name, kwargs in [
        ("trackableobjects:mobile:trackable_object_instance_registration_list", {"pk": trackable_object.pk}),
        ("trackableobjects:mobile:trackable_object_instance_activity_list", {"pk": trackable_object.pk}),
        ("trackableobjects:mobile:follow_up_event_list", {"pk": instance.pk}),
    ]:
        assert agent_client.get(reverse(name, kwargs=kwargs)).status_code == 200, name
