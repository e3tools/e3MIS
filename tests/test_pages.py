"""Characterization tests: every screen renders for the role it is meant for, and the other role is refused.

Written before the field monitoring merge so later changes (Django upgrade, PostGIS, new apps) can be
checked against today's behaviour.
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

STAFF_PAGES = [
    ("trackableobjects:trackable_object_list", {}),
    ("trackableobjects:trackable_object_create", {}),
    ("trackableobjects:follow_up_event_object_create", {}),
    ("trackableobjects:relationship_overview", {}),
    ("subprojects:subproject_list", {}),
    ("subprojects:subproject_dashboard", {}),
    ("subprojects:subproject_create", {}),
    ("subprojects:subproject_custom_fields", {}),
    ("subprojects:subproject_custom_fields_create", {}),
    ("subprojects:subproject_adminunit", {}),
    ("subprojects:contractor_list", {}),
    ("authorization:field_agent_list", {}),
    ("authorization:group_list", {}),
    ("authorization:app_settings", {}),
]

AGENT_PAGES = [
    ("trackableobjects:mobile:select-trackable-object", {}),
    ("trackableobjects:mobile:select_trackable_object_for_activity", {}),
    ("trackableobjects:mobile:all_activities", {}),
    ("subprojects:mobile:register-menu", {}),
    ("subprojects:mobile:select-subproject-for-activity", {}),
    ("subprojects:mobile:register-village-development-committee", {}),
]


@pytest.mark.parametrize("name,kwargs", STAFF_PAGES)
def test_staff_page_renders_for_staff(staff_client, name, kwargs):
    assert staff_client.get(reverse(name, kwargs=kwargs)).status_code == 200


@pytest.mark.parametrize("name,kwargs", STAFF_PAGES)
def test_staff_page_refused_for_field_agent(agent_client, name, kwargs):
    assert agent_client.get(reverse(name, kwargs=kwargs)).status_code == 403


@pytest.mark.parametrize("name,kwargs", AGENT_PAGES)
def test_agent_page_renders_for_field_agent(agent_client, name, kwargs):
    assert agent_client.get(reverse(name, kwargs=kwargs)).status_code == 200


@pytest.mark.parametrize("name,kwargs", AGENT_PAGES)
def test_agent_page_refused_for_staff(staff_client, name, kwargs):
    assert staff_client.get(reverse(name, kwargs=kwargs)).status_code == 403


def test_detail_pages_render_for_staff(staff_client, trackable_object, follow_up_event, instance, response):
    names = [
        ("trackableobjects:trackable_object_detail", trackable_object.pk),
        ("trackableobjects:trackable_object_edit", trackable_object.pk),
        ("trackableobjects:trackable_object_instance_detail", instance.pk),
        ("trackableobjects:follow_up_event_object_detail", follow_up_event.pk),
        ("trackableobjects:follow_up_event_object_edit", follow_up_event.pk),
        ("trackableobjects:follow_up_event_response_detail", response.pk),
        ("trackableobjects:relationship_object_detail", trackable_object.pk),
        ("trackableobjects:relationship_event_detail", follow_up_event.pk),
    ]
    for name, pk in names:
        assert staff_client.get(reverse(name, kwargs={"pk": pk})).status_code == 200, name


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_exports(staff_client, trackable_object, follow_up_event, instance, response, fmt):
    r = staff_client.get(reverse("trackableobjects:trackable_object_instances_export", kwargs={"pk": trackable_object.pk, "fmt": fmt}))
    assert r.status_code == 200
    r = staff_client.get(reverse("trackableobjects:follow_up_event_responses_export", kwargs={"pk": follow_up_event.pk, "fmt": fmt}))
    assert r.status_code == 200


def test_login_page_renders(client):
    assert client.get(reverse("authorization:login")).status_code == 200


def test_anonymous_is_sent_to_login(client):
    r = client.get(reverse("trackableobjects:trackable_object_list"))
    assert r.status_code == 302


def test_subproject_registration_needs_community_facilitator(agent, agent_client):
    from django.contrib.auth.models import Group

    url = reverse("subprojects:mobile:register-subproject")
    assert agent_client.get(url).status_code == 403
    agent.groups.add(Group.objects.get_or_create(name="Community facilitator")[0])
    assert agent_client.get(url).status_code == 200


def test_contractor_registration_for_technical_facilitator(agent_client):
    assert agent_client.get(reverse("subprojects:mobile:register-contractor")).status_code == 200


def test_logout_by_post(staff_client):
    r = staff_client.post(reverse("authorization:logout"))
    assert r.status_code == 302
    assert staff_client.get(reverse("trackableobjects:trackable_object_list")).status_code == 302
