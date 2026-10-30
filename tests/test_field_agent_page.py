"""The MIS field-agents page: a user is created with a role and one administrative unit.

25 Oct 2026 (Brice): role, commune and supervisor were only in the Django admin.
29 Oct 2026 (Brice): the commune list showed every unit, and reporting lines should follow from
role + unit. The unit is picked in the cascade; commune or region and the SC are worked out.
"""
import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from administrativelevels.models import AdministrativeLevel, AdministrativeUnit
from authorization.models import CustomUser, GroupRole, Role
from fieldmonitoring.core.geography import communes
from fieldmonitoring.core.models import ProgrammeConfig

URL = reverse("authorization:field_agent_list")
PASSWORD = "Terrain-2026-test"


@pytest.fixture
def tree(db):
    """Benin's shape: Département → Commune → Arrondissement → Village, levels configured."""
    levels = {
        name: AdministrativeLevel.objects.create(name=name, order=order)
        for name, order in [("Département", 10), ("Commune", 11), ("Arrondissement", 12), ("Village", 13)]
    }
    config = ProgrammeConfig.get()
    config.region_level, config.commune_level, config.village_level = (
        levels["Département"], levels["Commune"], levels["Village"]
    )
    config.save()
    region = AdministrativeUnit.objects.create(name="Littoral", level=levels["Département"])
    units = {"region": region}
    for name in ("Cotonou", "Abomey-Calavi"):
        commune = AdministrativeUnit.objects.create(name=name, level=levels["Commune"], parent=region)
        arrondissement = AdministrativeUnit.objects.create(
            name=f"{name} 1er", level=levels["Arrondissement"], parent=commune
        )
        units[name] = commune
        units[f"{name} village"] = AdministrativeUnit.objects.create(
            name=f"{name} centre", level=levels["Village"], parent=arrondissement
        )
    return units


def make_sc(commune, email="sc@example.test", name="Koffi"):
    user = CustomUser.objects.create_user(email=email, password="x", first_name=name, role=Role.SC, commune=commune)
    user.administrative_units.add(commune)
    return user


@pytest.fixture
def sc(tree):
    return make_sc(tree["Cotonou"])


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


def created():
    return CustomUser.objects.get(email="awa@example.test")


def test_facilitator_gets_commune_and_supervisor_from_the_unit(staff_client, tree, sc):
    response = staff_client.post(URL, payload(role="fc", administrative_units=[tree["Cotonou"].pk]))
    assert response.status_code == 302
    user = created()
    assert (user.role, user.commune, user.supervisor, user.is_field_agent) == (Role.FC, tree["Cotonou"], sc, True)
    assert list(user.administrative_units.all()) == [tree["Cotonou"]]
    assert user.check_password(PASSWORD)


def test_unit_inside_the_commune_gives_that_commune(staff_client, tree, sc):
    response = staff_client.post(URL, payload(role="ft", administrative_units=[tree["Cotonou village"].pk]))
    assert response.status_code == 302
    assert (created().commune, created().supervisor) == (tree["Cotonou"], sc)


def test_levels_configured_keep_arrondissements_out_of_communes(tree):
    # Without the setting, "parents of villages" made arrondissements look like communes.
    assert set(communes()) == {tree["Cotonou"], tree["Abomey-Calavi"]}


def test_facilitator_in_a_commune_without_sc_is_created_without_supervisor(staff_client, tree, sc):
    response = staff_client.post(URL, payload(role="fc", administrative_units=[tree["Abomey-Calavi"].pk]))
    assert response.status_code == 302
    assert (created().commune, created().supervisor) == (tree["Abomey-Calavi"], None)


def test_new_sc_takes_over_the_facilitators_of_their_commune(staff_client, tree):
    staff_client.post(URL, payload(role="fc", administrative_units=[tree["Abomey-Calavi"].pk]))
    response = staff_client.post(URL, payload(
        role="sc", email="sc2@example.test", administrative_units=[tree["Abomey-Calavi"].pk]
    ))
    assert response.status_code == 302
    assert created().supervisor == CustomUser.objects.get(email="sc2@example.test")


def test_supervisor_is_chosen_only_when_the_commune_has_several_scs(staff_client, tree, sc):
    second = make_sc(tree["Cotonou"], email="sc2@example.test", name="Seydou")
    response = staff_client.post(URL, payload(role="fc", administrative_units=[tree["Cotonou"].pk]))
    assert response.status_code == 200
    assert "supervisor" in response.context["form"].errors

    response = staff_client.post(URL, payload(
        role="fc", administrative_units=[tree["Cotonou"].pk], supervisor=second.pk
    ))
    assert response.status_code == 302
    assert created().supervisor == second


def test_moving_a_facilitator_changes_their_supervisor(staff_client, tree, sc):
    other = make_sc(tree["Abomey-Calavi"], email="sc2@example.test", name="Seydou")
    staff_client.post(URL, payload(role="fc", administrative_units=[tree["Cotonou"].pk]))
    user = created()
    response = staff_client.post(URL, payload(
        field_agent=user.pk, role="fc", administrative_units=[tree["Abomey-Calavi"].pk], password1="", password2=""
    ))
    assert response.status_code == 302
    user.refresh_from_db()
    assert (user.commune, user.supervisor) == (tree["Abomey-Calavi"], other)


def test_sc_who_moves_leaves_their_facilitators_to_nobody(staff_client, tree, sc):
    staff_client.post(URL, payload(role="fc", administrative_units=[tree["Cotonou"].pk]))
    response = staff_client.post(URL, {
        **payload(field_agent=sc.pk, email=sc.email, role="sc", password1="", password2=""),
        "administrative_units": [tree["Abomey-Calavi"].pk],
    })
    assert response.status_code == 302
    assert created().supervisor is None


def test_facilitator_cannot_be_attached_to_a_departement(staff_client, tree):
    response = staff_client.post(URL, payload(role="fc", administrative_units=[tree["region"].pk]))
    assert response.status_code == 200
    assert "administrative_units" in response.context["form"].errors
    assert not CustomUser.objects.filter(email="awa@example.test").exists()


def test_field_staff_have_exactly_one_unit(staff_client, tree):
    for units in ([], [tree["Cotonou"].pk, tree["Abomey-Calavi"].pk]):
        response = staff_client.post(URL, payload(role="sc", administrative_units=units))
        assert response.status_code == 200
        assert "administrative_units" in response.context["form"].errors


def test_regional_specialist_gets_the_region(staff_client, tree):
    response = staff_client.post(URL, payload(role="regional_specialist", administrative_units=[tree["region"].pk]))
    assert response.status_code == 302
    assert (created().region, created().commune, created().supervisor) == (tree["region"], None, None)


def test_national_specialist_needs_no_unit(staff_client, tree):
    response = staff_client.post(URL, payload(role="national_specialist"))
    assert response.status_code == 302
    assert (created().region, created().commune) == (None, None)


def test_new_agent_needs_a_role(staff_client, tree):
    response = staff_client.post(URL, payload(administrative_units=[tree["Cotonou"].pk]))
    assert response.status_code == 200
    assert "role" in response.context["form"].errors


def test_group_default_role_fills_the_role(staff_client, tree, sc, tf_group):
    GroupRole.objects.update_or_create(group=tf_group, defaults={"role": Role.FT})
    response = staff_client.post(URL, payload(groups=[tf_group.pk], administrative_units=[tree["Cotonou"].pk]))
    assert response.status_code == 302
    assert (created().role, created().supervisor) == (Role.FT, sc)


def test_refused_form_reopens_with_the_units_picked(staff_client, tree):
    response = staff_client.post(URL, payload(administrative_units=[tree["Cotonou"].pk]))
    assert list(response.context["posted_units"]) == [tree["Cotonou"]]
    assert b"modal('show')" in response.content


def test_existing_agent_without_role_can_still_be_edited(staff_client, agent):
    response = staff_client.post(
        URL,
        {"field_agent": agent.pk, "first_name": "Renamed", "last_name": "", "email": agent.email,
         "phone_number": "", "password1": "", "password2": ""},
    )
    assert response.status_code == 302
    agent.refresh_from_db()
    assert (agent.first_name, agent.role, agent.is_field_agent) == ("Renamed", "", True)


def test_page_gives_the_cascade_its_levels_and_the_role_groups(staff_client, tree, sc, tf_group):
    GroupRole.objects.update_or_create(group=tf_group, defaults={"role": Role.FT})
    response = staff_client.get(URL)
    assert response.context["role_groups"][Role.FT] == [tf_group.pk]
    assert response.context["group_roles"][tf_group.pk] == Role.FT
    assert response.context["level_orders"] == [10, 11, 12, 13]
    assert response.context["role_levels"][Role.SC] == 11
    assert response.context["role_levels"][Role.REGIONAL_SPECIALIST] == 10
    assert response.context["levels_configured"] is True
    assert "Koffi (Cotonou)" in response.content.decode()


def test_page_warns_while_levels_are_not_set(staff_client, db):
    response = staff_client.get(URL)
    assert response.context["levels_configured"] is False
    assert "alert-warning" in response.content.decode()


def test_group_page_sets_the_default_role(staff_client, db):
    staff_client.post(reverse("authorization:group_list"), {"group_id": "", "name": "Superviseurs", "role": "sc"})
    group = Group.objects.get(name="Superviseurs")
    assert group.field_role.role == Role.SC
    staff_client.post(reverse("authorization:group_list"), {"group_id": group.pk, "name": "Superviseurs", "role": ""})
    assert not GroupRole.objects.filter(group=group).exists()


def test_facilitator_groups_carry_their_role(db):
    # Migration 0012 sets them where the groups exist; the page relies on GroupRole only.
    from importlib import import_module

    from django.apps import apps

    tf = Group.objects.get_or_create(name="Community facilitator")[0]
    GroupRole.objects.filter(group=tf).delete()
    import_module("authorization.migrations.0012_group_role").set_group_roles(apps, None)
    assert GroupRole.objects.get(group=tf).role == Role.FC


def test_backfill_fills_units_communes_and_supervisors(tree, sc):
    legacy = CustomUser.objects.create_user(email="old@example.test", password="x", role=Role.FT,
                                            commune=tree["Cotonou"])
    by_unit = CustomUser.objects.create_user(email="unit@example.test", password="x", role=Role.SC)
    by_unit.administrative_units.add(tree["Abomey-Calavi village"])

    call_command("backfill_user_scope", stdout=open("/dev/null", "w"))
    legacy.refresh_from_db()
    assert (list(legacy.administrative_units.all()), legacy.supervisor) == ([], None)  # report only

    call_command("backfill_user_scope", "--apply", stdout=open("/dev/null", "w"))
    legacy.refresh_from_db()
    by_unit.refresh_from_db()
    assert list(legacy.administrative_units.all()) == [tree["Cotonou"]]
    assert legacy.supervisor == sc
    assert by_unit.commune == tree["Abomey-Calavi"]


def test_set_programme_levels_command(db):
    for name, order in [("Département", 1), ("Commune", 2), ("Village", 4)]:
        AdministrativeLevel.objects.create(name=name, order=order)
    call_command("set_programme_levels", "--region", "département", "--commune", "Commune", "--village", "Village",
                 stdout=open("/dev/null", "w"))
    config = ProgrammeConfig.get()
    assert (config.region_level.name, config.commune_level.name, config.village_level.name) == (
        "Département", "Commune", "Village"
    )
