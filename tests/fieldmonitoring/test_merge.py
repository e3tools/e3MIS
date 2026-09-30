"""Behaviour specific to running field monitoring inside the MIS."""
import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from administrativelevels.models import AdministrativeLevel, AdministrativeUnit
from authorization.models import Role, User
from fieldmonitoring.core.geography import commune_of, region_of, villages_under
from fieldmonitoring.core.models import ProgrammeConfig
from fieldmonitoring.registry.models import Worksite

from .conftest import make_user

pytestmark = pytest.mark.django_db


class TestSignIn:
    url = "/api/v1/auth/token/"

    def test_email_signs_in(self, sc):
        r = APIClient().post(self.url, {"email": sc.email, "password": "pw"}, format="json")
        assert r.status_code == 200 and "access" in r.json()

    def test_old_app_builds_send_the_email_as_username(self, sc):
        r = APIClient().post(self.url, {"username": sc.email, "password": "pw"}, format="json")
        assert r.status_code == 200

    def test_matching_is_exact(self, sc):
        r = APIClient().post(self.url, {"username": sc.email.upper(), "password": "pw"}, format="json")
        assert r.status_code == 401

    def test_missing_identifier_is_400(self):
        assert APIClient().post(self.url, {"password": "pw"}, format="json").status_code == 400

    def test_me_reports_string_id_and_username(self, sc, client_for):
        body = client_for(sc).get("/api/v1/auth/me/").json()
        assert body["id"] == str(sc.id) and body["username"] == sc.email
        assert body["commune"] == "Dabou" and body["role"] == "sc"


class TestRoles:
    def test_visiting_roles_are_field_agents(self, ft, sc, regional, rdp):
        assert ft.is_field_agent and sc.is_field_agent and regional.is_field_agent
        assert not rdp.is_field_agent

    def test_users_without_a_role_keep_their_mis_flag(self, db):
        user = User.objects.create_user(email="desk@example.test", password="x", is_field_agent=True)
        assert user.role == "" and user.is_field_agent

    def test_backfill_migration_maps_facilitator_groups(self, db):
        from importlib import import_module

        from django.apps import apps
        from django.contrib.auth.models import Group

        backfill = import_module("authorization.migrations.0011_backfill_roles_from_groups").backfill
        tf = User.objects.create_user(email="tf@example.test", password="x", is_field_agent=True)
        both = User.objects.create_user(email="both@example.test", password="x", is_field_agent=True)
        tf_group = Group.objects.get_or_create(name="Technical facilitator")[0]
        cf_group = Group.objects.get_or_create(name="Community facilitator")[0]
        tf.groups.add(tf_group)
        both.groups.add(tf_group, cf_group)
        backfill(apps, None)
        tf.refresh_from_db()
        both.refresh_from_db()
        assert tf.role == Role.FT and both.role == ""


class TestGeography:
    def test_worksite_derives_commune_and_region_from_its_village(self, worksite, commune, region):
        assert worksite.commune == commune and worksite.region == region

    def test_without_level_mapping_the_tree_position_is_used(self, db):
        config = ProgrammeConfig.get()
        assert config.commune_level_id is None
        level = AdministrativeLevel.objects.create(name="Département", order=1)
        dep = AdministrativeUnit.objects.create(name="Atlantique", level=level)
        com = AdministrativeUnit.objects.create(name="Abomey-Calavi", level=level, parent=dep)
        arr = AdministrativeUnit.objects.create(name="Godomey", level=level, parent=com)
        assert commune_of(arr) == com and region_of(arr) == dep
        assert list(villages_under(com)) == [arr]

    def test_villages_under_a_commune_are_its_village_level_units(self, commune, village, other_commune, levels):
        AdministrativeUnit.objects.create(name="Ailleurs", level=levels["village"], parent=other_commune)
        assert list(villages_under(commune)) == [village]

    def test_villages_endpoint_lists_units_in_my_commune(self, ft, village, client_for):
        assert client_for(ft).get("/api/v1/villages/").json() == [{"id": str(village.id), "name": village.name}]

    def test_worksite_can_link_to_a_subproject(self, worksite):
        from subprojects.models import Subproject

        sub = Subproject.objects.create(external_id="SP-1", name="Forage", administrative_level=worksite.village)
        worksite.subproject = sub
        worksite.save()
        assert sub.worksites.get() == worksite


def test_api_lives_outside_the_language_prefix(client_for, sc):
    assert client_for(sc).get("/api/v1/me/worksites/").status_code == 200
    assert APIClient().get("/api/v1/health/").status_code == 200


def test_seed_demo_runs_on_an_empty_database(capsys):
    call_command("seed_demo", password="demo-pass-123")
    koffi = User.objects.get(email="koffi@example.org")
    assert koffi.role == Role.SC and koffi.administrative_units.filter(name="Dabou").exists()
    ibrahim = User.objects.get(email="ibrahim@example.org")
    assert ibrahim.groups.filter(name="Technical facilitator").exists()
    assert Worksite.objects.filter(commune__name="Dabou").exists()
    r = APIClient().post("/api/v1/auth/token/", {"username": "koffi@example.org", "password": "demo-pass-123"}, format="json")
    assert r.status_code == 200


@pytest.mark.parametrize("header", [None, "Bearer not-a-valid-jwt"])
def test_signed_out_or_expired_is_401_so_apps_refresh(header):
    client = APIClient()
    if header:
        client.credentials(HTTP_AUTHORIZATION=header)
    r = client.get("/api/v1/me/worksites/")
    assert r.status_code == 401 and r["WWW-Authenticate"].startswith("Bearer")
