"""Administrative units added in bulk from an Excel file (Nov 2026).

The template holds the current tree (one row per unit at the bottom of its branch) and an optional
Zone column. The import only adds: existing units are recognised whatever the case, and the zone of a
village may change, with the radius of its unconfirmed worksites.
"""
from io import BytesIO

import pytest
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook, load_workbook

from administrativelevels.models import RURAL, URBAN, AdministrativeLevel, AdministrativeUnit
from authorization.models import CustomUser
from fieldmonitoring.core.models import ProgrammeConfig
from fieldmonitoring.registry.models import Worksite
from tests.conftest import client_for

PAGE = reverse("administrativelevels:administrative_unit_import")
CONFIRM = reverse("administrativelevels:administrative_unit_import_confirm")
TEMPLATE = reverse("administrativelevels:administrative_unit_import_template")
ROOT = reverse("administrativelevels:administrative_unit_root")
LEVELS = ["Department", "Commune", "Arrondissement", "Village"]


@pytest.fixture
def tree(db):
    levels = [AdministrativeLevel.objects.create(name=name, order=order) for order, name in enumerate(LEVELS, 1)]
    config = ProgrammeConfig.get()
    config.region_level, config.commune_level, config.village_level = levels[0], levels[1], levels[3]
    config.save()
    borgou = AdministrativeUnit.objects.create(name="BORGOU", level=levels[0])
    nikki = AdministrativeUnit.objects.create(name="NIKKI", level=levels[1], parent=borgou)
    ouenou = AdministrativeUnit.objects.create(name="OUÉNOU", level=levels[2], parent=nikki)
    gah = AdministrativeUnit.objects.create(name="GAH", level=levels[3], parent=ouenou, zone=RURAL)
    # A commune with nothing under it yet: its own row in the template.
    kalale = AdministrativeUnit.objects.create(name="KALALÈ", level=levels[1], parent=borgou)
    return {"levels": levels, "BORGOU": borgou, "NIKKI": nikki, "OUÉNOU": ouenou, "GAH": gah, "KALALÈ": kalale}


@pytest.fixture
def desk_user(db):
    return CustomUser.objects.create_user(email="desk@example.test", password="x")


def template(client):
    response = client.get(TEMPLATE)
    assert response.status_code == 200
    return load_workbook(BytesIO(response.content))


def as_upload(workbook):
    out = BytesIO()
    workbook.save(out)
    return SimpleUploadedFile("units.xlsx", out.getvalue())


def add_rows(workbook, rows):
    sheet = workbook["Unités"]
    for values in rows:
        sheet.append(values)
    return as_upload(workbook)


def upload(client, file):
    return client.post(PAGE, {"file": file})


def errors_of(response):
    return [f"{e['row']} {e['column']}: {e['message']}" for e in response.context.get("errors") or []]


def paths():
    return sorted(unit.hierarchy_name or unit.name for unit in AdministrativeUnit.objects.all())


# --- Access ------------------------------------------------------------------------------------

@pytest.mark.parametrize("url", [PAGE, TEMPLATE])
def test_only_django_admin_users_can_import_units(url, desk_user, staff_client, tree):
    agent = CustomUser.objects.create_user(email="ft@example.test", password="x", is_field_agent=True)
    assert client_for(desk_user).get(url).status_code == 403
    assert client_for(agent).get(url).status_code == 403
    assert staff_client.get(url).status_code == 200
    assert client_for(desk_user).post(CONFIRM, {}).status_code == 403


def test_import_button_on_the_units_page_only_for_django_admin_users(desk_user, staff_client, tree):
    assert PAGE in staff_client.get(ROOT).content.decode()
    assert PAGE not in client_for(desk_user).get(ROOT).content.decode()


# --- Template ----------------------------------------------------------------------------------

def test_template_holds_the_current_tree_with_zones(staff_client, tree):
    workbook = template(staff_client)
    assert workbook.sheetnames == ["Instructions", "Unités"]
    rows = [list(row) for row in workbook["Unités"].iter_rows(values_only=True)]
    assert rows == [
        LEVELS + ["Zone"],
        ["BORGOU", "KALALÈ", None, None, None],
        ["BORGOU", "NIKKI", "OUÉNOU", "GAH", "Rurale"],
    ]
    validation = workbook["Unités"].data_validations.dataValidation[0]
    assert validation.formula1 == '"Urbaine,Rurale"'
    assert "E2" in validation.sqref


def test_instructions_wrap_with_room_for_every_line(staff_client, tree):
    """Excel does not resize rows written by openpyxl: the heights are set, so nothing is cut."""
    for url in (TEMPLATE, reverse("authorization:field_agent_import_template")):
        sheet = load_workbook(BytesIO(staff_client.get(url).content))["Instructions"]
        long_rows = [row for row in range(1, sheet.max_row + 1) if len(str(sheet.cell(row, 1).value or "")) > 110]
        assert long_rows
        for row in long_rows:
            assert sheet.cell(row, 1).alignment.wrap_text
            assert sheet.row_dimensions[row].height >= 30


# --- Upload and creation -----------------------------------------------------------------------

def test_new_units_are_previewed_then_created_and_existing_ones_recognised(staff_client, tree):
    file = add_rows(template(staff_client), [
        ["Borgou", "nikki", "Ouénou ", "SANSI", "Urbaine"],      # under existing units, whatever the case
        ["BORGOU", "KALALÈ", "BOUCA", "GAH"],                    # same village name, other branch
        ["BORGOU", "KALALÈ", "BOUCA", "DUNKASSA"],
        ["ALIBORI", "KANDI"],                                    # a new branch, stopping at the commune
    ])
    response = upload(staff_client, file)
    assert errors_of(response) == []
    summary = response.context["summary"]
    assert [(level["name"], level["new"], level["existing"]) for level in summary["levels"]] == [
        ("Department", 1, 1), ("Commune", 1, 2), ("Arrondissement", 1, 1), ("Village", 3, 1),
    ]
    assert "BORGOU → KALALÈ → BOUCA → DUNKASSA" in summary["new_units"]
    assert AdministrativeUnit.objects.count() == 5

    response = staff_client.post(CONFIRM)
    assert response.status_code == 302
    sansi = AdministrativeUnit.objects.get(name="SANSI")
    assert (sansi.parent, sansi.zone, sansi.level.name) == (tree["OUÉNOU"], URBAN, "Village")
    assert AdministrativeUnit.objects.filter(name="GAH").count() == 2
    assert AdministrativeUnit.objects.get(name="KANDI").parent.name == "ALIBORI"
    assert AdministrativeUnit.objects.count() == 11

    # The next template holds them; uploading it again creates nothing.
    response = upload(staff_client, as_upload(template(staff_client)))
    assert len(response.context["summary"]["new_units"]) == 0


def test_a_file_in_the_sync_command_layout_is_accepted(staff_client, tree):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Administrative Hierarchy"
    sheet.append(LEVELS)
    sheet.append(["BORGOU", "NIKKI", "OUÉNOU", "TONTAROU"])
    response = upload(staff_client, as_upload(workbook))
    assert response.context["summary"]["new_units"] == ["BORGOU → NIKKI → OUÉNOU → TONTAROU"]


def test_errors_are_listed_with_row_and_column(staff_client, tree):
    file = add_rows(template(staff_client), [
        ["BORGOU", "", "OUÉNOU", "X"],
        ["BORGOU", "NIKKI", "OUÉNOU", "", "Urbaine"],
        ["BORGOU", "NIKKI", "OUÉNOU", "Y", "Ville"],
    ])
    response = upload(staff_client, file)
    assert errors_of(response) == [
        "4 Commune: Vide, alors qu’un niveau à sa droite est rempli : "
        "écrivez le chemin complet depuis le premier niveau.",
        "6 Zone: « Ville » n’est pas une zone : choisissez Urbaine ou Rurale.",
    ]
    # Once the layout is right, the zone rules are checked.
    file = add_rows(template(staff_client), [
        ["BORGOU", "NIKKI", "OUÉNOU", "", "Urbaine"],
        ["BORGOU", "NIKKI", "OUÉNOU", "Z", "Urbaine"],
        ["BORGOU", "NIKKI", "OUÉNOU", "z", "Rurale"],
    ])
    response = upload(staff_client, file)
    assert errors_of(response) == [
        "4 Zone: Une zone ne concerne qu’une unité du niveau Village : laissez-la vide sur cette ligne.",
        "6 Zone: Une autre ligne donne une zone différente à cette unité (ligne 5).",
    ]
    assert staff_client.post(CONFIRM).status_code == 302
    assert AdministrativeUnit.objects.count() == 5


def test_renamed_columns_are_refused(staff_client, tree):
    workbook = template(staff_client)
    workbook["Unités"]["B1"] = "Communes"
    response = upload(staff_client, as_upload(workbook))
    assert errors_of(response)[0].startswith("1 Communes: La colonne « Communes » devrait être « Commune ».")


def test_a_zone_change_moves_the_radius_of_unconfirmed_worksites(staff_client, tree):
    config = ProgrammeConfig.get()
    pending = Worksite.objects.create(name="Pending", village=tree["GAH"], location=None)
    placed = Worksite.objects.create(name="Placed", village=tree["GAH"], location=Point(2.6, 9.9, srid=4326))
    assert pending.tolerance_m == config.rural_tolerance_m

    workbook = template(staff_client)
    workbook["Unités"]["E3"] = "Urbaine"
    response = upload(staff_client, as_upload(workbook))
    assert (response.context["summary"]["zones"], response.context["summary"]["radii"]) == (1, 1)
    staff_client.post(CONFIRM)

    tree["GAH"].refresh_from_db()
    pending.refresh_from_db()
    placed.refresh_from_db()
    assert tree["GAH"].zone == URBAN
    assert pending.tolerance_m == config.urban_tolerance_m
    assert placed.tolerance_m == config.rural_tolerance_m


def test_an_empty_zone_cell_keeps_the_zone(staff_client, tree):
    workbook = template(staff_client)
    workbook["Unités"]["E3"] = None
    upload(staff_client, as_upload(workbook))
    staff_client.post(CONFIRM)
    tree["GAH"].refresh_from_db()
    assert tree["GAH"].zone == RURAL


def test_confirm_without_a_checked_file(staff_client, tree):
    response = staff_client.post(CONFIRM)
    assert response.status_code == 302
    assert response.url == PAGE


@pytest.mark.parametrize("name, on_unit", [
    ("administrativelevels:administrative_levels_list", False),
    ("administrativelevels:administrative_unit_root", False),
    ("administrativelevels:administrative_unit_detail", True),
])
def test_unit_and_level_pages_are_closed_to_field_agents(name, on_unit, desk_user, tree):
    url = reverse(name, kwargs={"pk": tree["NIKKI"].pk} if on_unit else {})
    agent = CustomUser.objects.create_user(email="ft@example.test", password="x", is_field_agent=True)
    assert client_for(agent).get(url).status_code == 403
    assert client_for(agent).post(url, {"action": "delete_self"}).status_code == 403
    assert client_for(desk_user).get(url).status_code == 200
    assert AdministrativeUnit.objects.filter(pk=tree["NIKKI"].pk).exists()
