"""Access rules added in Phase 0: every screen and endpoint checks who is asking."""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from trackableobjects.models import FollowUpEvent, TrackableObject

from .conftest import client_for

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("name,model", [
    ("trackableobjects:trackable_object_delete", "trackable_object"),
    ("trackableobjects:follow_up_event_object_delete", "follow_up_event"),
])
def test_delete_needs_admin(request, agent, staff_user, name, model):
    obj = request.getfixturevalue(model)
    url = reverse(name, kwargs={"pk": obj.pk})
    assert client_for(agent).post(url).status_code == 403
    assert client_for(staff_user).post(url).status_code == 403  # desktop user, not Admin
    staff_user.groups.add(Group.objects.get_or_create(name="Admin")[0])
    assert client_for(staff_user).post(url).status_code == 302
    assert not type(obj).objects.filter(pk=obj.pk).exists()


def test_anonymous_cannot_delete(client, trackable_object):
    r = client.post(reverse("trackableobjects:trackable_object_delete", kwargs={"pk": trackable_object.pk}))
    assert r.status_code == 302 and "next=" in r.url
    assert TrackableObject.objects.filter(pk=trackable_object.pk).exists()


def test_superuser_can_delete(superuser, follow_up_event):
    r = client_for(superuser).post(reverse("trackableobjects:follow_up_event_object_delete", kwargs={"pk": follow_up_event.pk}))
    assert r.status_code == 302
    assert not FollowUpEvent.objects.exists()


def test_follow_up_event_list_is_for_desktop_users(staff_client, agent_client):
    url = reverse("trackableobjects:follow_up_event_list")
    assert staff_client.get(url).status_code == 200
    assert agent_client.get(url).status_code == 403


@pytest.mark.parametrize("name", ["subprojects:contractor_list"])
def test_anonymous_is_sent_to_login(client, name):
    r = client.get(reverse(name))
    assert r.status_code == 302 and "next=" in r.url


class TestInstanceListEndpoint:
    url = "/fr/trackable-objects/api/trackable-object-instance"

    def test_needs_sign_in(self, client, instance):
        assert client.get(self.url, {"trackable-object": instance.trackable_object_id}).status_code == 401

    def test_uses_the_signed_in_agent_not_a_header(self, agent_client, other_agent, instance):
        r = agent_client.get(self.url, {"administrative-unit": "", "trackable-object": instance.trackable_object_id})
        assert [i["id"] for i in r.json()] == [instance.pk]
        # Another agent (no units) sees nothing, even when claiming to be the first agent in a header.
        r = client_for(other_agent).get(
            self.url, {"administrative-unit": "", "trackable-object": instance.trackable_object_id},
            HTTP_USER=str(instance.created_by_id),
        )
        assert r.json() == []

    def test_agent_cannot_query_a_unit_outside_theirs(self, other_agent, unit, instance):
        r = client_for(other_agent).get(self.url, {"administrative-unit": unit.pk, "trackable-object": instance.trackable_object_id})
        assert r.status_code == 403

    def test_missing_parameters_are_a_400_not_a_crash(self, agent_client):
        assert agent_client.get(self.url).status_code == 400


def test_admin_unit_api_needs_sign_in(client, agent_client, unit):
    url = reverse("administrativelevels:api:administrative-unit-root")
    assert client.get(url).status_code == 401
    assert agent_client.get(url).status_code == 200


def test_subproject_custom_fields_missing_unit_is_404(agent_client):
    assert agent_client.get(reverse("subprojects:api:custom-fields")).status_code == 404
