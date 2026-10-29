"""The MIS field-agents page sets the field monitoring role, commune and supervisor (Brice, 25 Oct 2026).

Before, those were only in the Django admin, so agents created from this page had no role.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from administrativelevels.models import AdministrativeLevel, AdministrativeUnit
from authorization.models import CustomUser, Role

URL = reverse("authorization:field_agent_list")
PASSWORD = "Terrain-2026-test"


@pytest.fixture
def tree(db):
    region_level = AdministrativeLevel.objects.create(name="Département", order=10)
    commune_level = AdministrativeLevel.objects.create(name="Commune", order=11)
    village_level = AdministrativeLevel.objects.create(name="Village", order=12)
    region = AdministrativeUnit.objects.create(name="Littoral", level=region_level)
    communes = {}
    for name in ("Cotonou", "Abomey-Calavi"):
        communes[name] = AdministrativeUnit.objects.create(name=name, level=commune_level, parent=region)
        AdministrativeUnit.objects.create(name=f"{name} centre", level=village_level, parent=communes[name])
    return region, communes


@pytest.fixture
def sc(tree):
    _, communes = tree
    return CustomUser.objects.create_user(
        email="sc@example.test", password="x", first_name="Koffi", role=Role.SC, commune=communes["Cotonou"]
    )


def payload(**extra):
    data = {
        "field_agent": "",
        "first_name": "Awa",
        "last_name": "Test",
        "email": "awa@example.test",
        "phone_number": "",
        "password1": PASSWORD,
        "password2": PASSWORD,
    }
    data.update(extra)
    return data


def test_create_facilitator_with_role_commune_and_supervisor(staff_client, tree, sc):
    _, communes = tree
    response = staff_client.post(
        URL, payload(role="fc", commune=communes["Cotonou"].pk, supervisor=sc.pk)
    )
    assert response.status_code == 302
    user = CustomUser.objects.get(email="awa@example.test")
    assert (user.role, user.commune, user.supervisor, user.is_field_agent) == (
        Role.FC, communes["Cotonou"], sc, True
    )
    assert user.check_password(PASSWORD)


def test_create_supervisor(staff_client, tree):
    _, communes = tree
    response = staff_client.post(URL, payload(role="sc", commune=communes["Cotonou"].pk))
    assert response.status_code == 302
    user = CustomUser.objects.get(email="awa@example.test")
    assert (user.role, user.commune, user.supervisor) == (Role.SC, communes["Cotonou"], None)


def test_new_agent_needs_a_role(staff_client, tree):
    response = staff_client.post(URL, payload())
    assert response.status_code == 200
    assert "role" in response.context["form"].errors
    assert not CustomUser.objects.filter(email="awa@example.test").exists()


def test_facilitator_needs_a_supervisor(staff_client, tree):
    _, communes = tree
    response = staff_client.post(URL, payload(role="ft", commune=communes["Cotonou"].pk))
    assert response.status_code == 200
    assert "supervisor" in response.context["form"].errors
    assert not CustomUser.objects.filter(email="awa@example.test").exists()


def test_supervisor_must_be_in_the_same_commune(staff_client, tree, sc):
    _, communes = tree
    response = staff_client.post(
        URL, payload(role="fc", commune=communes["Abomey-Calavi"].pk, supervisor=sc.pk)
    )
    assert response.status_code == 200
    assert "supervisor" in response.context["form"].errors


def test_refused_form_reopens_with_the_units_picked(staff_client, tree):
    _, communes = tree
    response = staff_client.post(URL, payload(administrative_units=[communes["Cotonou"].pk]))
    assert list(response.context["posted_units"]) == [communes["Cotonou"]]
    assert b"modal('show')" in response.content


def test_fields_the_role_does_not_use_are_cleared(staff_client, tree, sc):
    region, communes = tree
    response = staff_client.post(
        URL, payload(role="sc", commune=communes["Cotonou"].pk, supervisor=sc.pk, region=region.pk)
    )
    assert response.status_code == 302
    user = CustomUser.objects.get(email="awa@example.test")
    assert (user.supervisor, user.region) == (None, None)


def test_existing_agent_without_role_can_still_be_edited(staff_client, agent):
    response = staff_client.post(
        URL,
        {"field_agent": agent.pk, "first_name": "Renamed", "last_name": "", "email": agent.email,
         "phone_number": "", "password1": "", "password2": ""},
    )
    assert response.status_code == 302
    agent.refresh_from_db()
    assert (agent.first_name, agent.role, agent.is_field_agent) == ("Renamed", "", True)


def test_page_lists_roles_and_offers_the_role_groups(staff_client, tree, sc, tf_group):
    Group.objects.get_or_create(name="Community facilitator")
    response = staff_client.get(URL)
    assert response.context["role_groups"] == {Role.FT: tf_group.pk,
                                               Role.FC: Group.objects.get(name="Community facilitator").pk}
    assert "Koffi (Cotonou)" in response.content.decode()
