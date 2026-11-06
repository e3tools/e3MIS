"""Field agents created in bulk from an Excel file (Nov 2026).

The template is built from the database (groups, units, SCs as drop-down lists, the units in a
cascade). The upload is checked with the field-agents page's own form, then a shared password is
asked and every agent is created, or none.
"""
from io import BytesIO

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import load_workbook

from administrativelevels.models import AdministrativeLevel, AdministrativeUnit
from authorization.models import CustomUser, GroupRole, Role
from fieldmonitoring.core.models import ProgrammeConfig
from tests.conftest import client_for

PAGE = reverse("authorization:field_agent_import")
CONFIRM = reverse("authorization:field_agent_import_confirm")
TEMPLATE = reverse("authorization:field_agent_import_template")
PASSWORD = "Terrain-2026-import"


@pytest.fixture
def tree(db):
    """Département → Commune → Arrondissement → Village, with a village name used in two communes."""
    levels = {
        name: AdministrativeLevel.objects.create(name=name, order=order)
        for name, order in [("Department", 10), ("Commune", 11), ("Arrondissement", 12), ("Village", 13)]
    }
    config = ProgrammeConfig.get()
    config.region_level, config.commune_level, config.village_level = (
        levels["Department"], levels["Commune"], levels["Village"]
    )
    config.save()
    units = {"Borgou": AdministrativeUnit.objects.create(name="Borgou", level=levels["Department"])}
    for commune_name, arrondissement_name in (("Nikki", "Nikki-Centre"), ("Kalalè", "Bouca")):
        commune = AdministrativeUnit.objects.create(name=commune_name, level=levels["Commune"], parent=units["Borgou"])
        arrondissement = AdministrativeUnit.objects.create(
            name=arrondissement_name, level=levels["Arrondissement"], parent=commune
        )
        units[commune_name] = commune
        units[arrondissement_name] = arrondissement
        # Same name in both communes: only the path tells them apart.
        units[f"{commune_name}/Gah"] = AdministrativeUnit.objects.create(
            name="Gah", level=levels["Village"], parent=arrondissement
        )
        units[f"{commune_name}/other"] = AdministrativeUnit.objects.create(
            name=f"{commune_name} Sud", level=levels["Village"], parent=arrondissement
        )
    return units


@pytest.fixture
def fc_group(db):
    """Created by the migrations, with its default role (FC)."""
    group = Group.objects.get_or_create(name="Community facilitator")[0]
    GroupRole.objects.get_or_create(group=group, defaults={"role": Role.FC})
    return group


@pytest.fixture
def desk_user(db):
    """A desktop (MIS) user without Django admin access."""
    return CustomUser.objects.create_user(email="desk@example.test", password="x")


def make_sc(commune, email, name):
    user = CustomUser.objects.create_user(email=email, password="x", first_name=name, last_name="SC",
                                          role=Role.SC, commune=commune)
    user.administrative_units.add(commune)
    return user


def template(client):
    response = client.get(TEMPLATE)
    assert response.status_code == 200
    return load_workbook(BytesIO(response.content))


def fill(workbook, agents=(), assignments=()):
    """Writes rows below the headers; returns the file as an upload."""
    for row, values in enumerate(agents, start=2):
        for col, value in enumerate(values, start=1):
            workbook["Agents"].cell(row=row, column=col, value=value)
    for row, values in enumerate(assignments, start=2):
        for col, value in enumerate(values, start=1):
            workbook["Affectations"].cell(row=row, column=col, value=value)
    out = BytesIO()
    workbook.save(out)
    return SimpleUploadedFile("agents.xlsx", out.getvalue())


def upload(client, file):
    return client.post(PAGE, {"file": file})


def errors_of(response):
    return [f"{e['sheet']} {e['row']} {e['column']}: {e['message']}" for e in response.context.get("errors") or []]


# --- Access ------------------------------------------------------------------------------------

@pytest.mark.parametrize("url", [PAGE, TEMPLATE])
def test_only_django_admin_users_can_import(url, desk_user, staff_client, tree):
    agent = CustomUser.objects.create_user(email="ft@example.test", password="x", is_field_agent=True)
    assert client_for(desk_user).get(url).status_code == 403
    assert client_for(agent).get(url).status_code == 403
    assert staff_client.get(url).status_code == 200


def test_confirm_refused_to_desktop_users(desk_user):
    assert client_for(desk_user).post(CONFIRM, {}).status_code == 403


def test_import_button_only_for_django_admin_users(desk_user, staff_client, tree):
    list_url = reverse("authorization:field_agent_list")
    assert PAGE in staff_client.get(list_url).content.decode()
    assert PAGE not in client_for(desk_user).get(list_url).content.decode()


def test_import_closed_while_levels_are_not_set(staff_client, tree):
    ProgrammeConfig.objects.update(region_level=None, commune_level=None, village_level=None)
    response = upload(staff_client, fill(template(staff_client), [["Awa", "Bio", "awa@example.test"]]))
    assert not CustomUser.objects.filter(email="awa@example.test").exists()
    assert "import stays closed" in response.content.decode() or "reste fermé" in response.content.decode()


# --- Template ----------------------------------------------------------------------------------

def test_template_lists_current_roles_groups_scs_and_units(staff_client, tree, fc_group):
    make_sc(tree["Nikki"], "sc.nikki@example.test", "Bio")
    workbook = template(staff_client)
    assert workbook.sheetnames == ["Instructions", "Agents", "Affectations", "Lists"]
    assert workbook["Lists"].sheet_state == "hidden"
    lists = workbook["Lists"]
    column = {letter: [c.value for c in lists[letter][1:] if c.value is not None] for letter in "ABCDFGI"}
    assert "Facilitateur communautaire" in column["A"]
    assert column["B"] == sorted(Group.objects.values_list("name", flat=True))
    assert column["C"] == ["Bio SC (sc.nikki@example.test)"]
    assert column["D"] == ["Borgou"]
    # Children keyed by their parent's path: both "Gah" villages, each under its own arrondissement.
    pairs = list(zip(column["F"], column["G"]))
    assert ("Borgou|Nikki|Nikki-Centre", "Gah") in pairs
    assert ("Borgou|Kalalè|Bouca", "Gah") in pairs
    assert [c.value for c in workbook["Affectations"][1]] == ["E-mail de l'agent",
                                                              "Department", "Commune", "Arrondissement", "Village"]


def test_template_cascade_reads_the_units_on_the_left(staff_client, tree):
    validations = template(staff_client)["Affectations"].data_validations.dataValidation
    formulas = {str(v.sqref).split(":")[0]: v.formula1 for v in validations}
    assert formulas["B2"] == "Lists!$D$2:$D$2"
    assert formulas["D2"] == (
        'OFFSET(Lists!$G$1,VLOOKUP($B2&"|"&$C2,Lists!$I:$K,2,0)-1,0,VLOOKUP($B2&"|"&$C2,Lists!$I:$K,3,0),1)'
    )
    index = {row[0]: (row[1], row[2]) for row in template(staff_client)["Lists"].iter_rows(
        min_row=2, min_col=9, max_col=11, values_only=True) if row[0]}
    lists = template(staff_client)["Lists"]
    start, count = index["Borgou|Nikki|Nikki-Centre"]
    assert sorted(lists[f"G{row}"].value for row in range(start, start + count)) == ["Gah", "Nikki Sud"]


def test_a_new_group_appears_in_the_next_template(staff_client, tree):
    Group.objects.create(name="Animateurs 2027")
    assert "Animateurs 2027" in [c.value for c in template(staff_client)["Lists"]["B"]]


# --- Check and creation ------------------------------------------------------------------------

def test_sc_and_facilitators_of_one_file_are_linked_then_created_with_the_password(staff_client, tree, fc_group):
    file = fill(
        template(staff_client),
        agents=[
            ["Awa", "Bio", "awa@example.test", "22997000001", "", "Community facilitator", ""],
            ["Koffi", "Sare", "koffi@example.test", "", "Superviseur communal", "", ""],
        ],
        assignments=[
            ["awa@example.test", "Borgou", "Nikki", "Nikki-Centre", "Gah"],
            ["awa@example.test", "Borgou", "Nikki", "Nikki-Centre", "Nikki Sud"],
            ["koffi@example.test", "Borgou", "Nikki"],
        ],
    )
    response = upload(staff_client, file)
    assert errors_of(response) == []
    preview = {result["email"]: result for result in response.context["results"]}
    assert preview["awa@example.test"]["commune"] == "Nikki"
    assert preview["awa@example.test"]["supervisor"] == "Koffi Sare (koffi@example.test)"
    assert preview["awa@example.test"]["role"] == "Facilitateur communautaire"  # from the group
    assert not CustomUser.objects.filter(email__in=["awa@example.test", "koffi@example.test"]).exists()

    response = staff_client.post(CONFIRM, {"password1": PASSWORD, "password2": PASSWORD})
    assert response.status_code == 302
    awa, koffi = CustomUser.objects.get(email="awa@example.test"), CustomUser.objects.get(email="koffi@example.test")
    assert awa.supervisor == koffi and awa.commune == tree["Nikki"] and awa.role == Role.FC
    assert awa.is_field_agent and awa.phone_number == "22997000001"
    assert set(awa.administrative_units.all()) == {tree["Nikki/Gah"], tree["Nikki/other"]}
    assert list(awa.groups.all()) == [fc_group]
    assert awa.check_password(PASSWORD) and koffi.check_password(PASSWORD)
    assert koffi.commune == tree["Nikki"] and koffi.supervisor is None
    assert "field_agent_import" not in staff_client.session


def test_existing_facilitators_go_to_an_sc_created_by_the_file(staff_client, tree):
    waiting = CustomUser.objects.create_user(email="waiting@example.test", password="x", role=Role.FT,
                                             commune=tree["Kalalè"])
    file = fill(template(staff_client), [["Koffi", "Sare", "koffi@example.test", "", "Superviseur communal"]],
                [["koffi@example.test", "Borgou", "Kalalè"]])
    upload(staff_client, file)
    staff_client.post(CONFIRM, {"password1": PASSWORD, "password2": PASSWORD})
    waiting.refresh_from_db()
    assert waiting.supervisor.email == "koffi@example.test"


def test_errors_name_the_sheet_row_and_column_and_nothing_is_created(staff_client, tree, fc_group):
    CustomUser.objects.create_user(email="Taken@Example.test", password="x")
    file = fill(
        template(staff_client),
        agents=[
            ["Awa", "Bio", "taken@example.test", "", "Facilitateur communautaire"],
            ["Ali", "", "ali@example.test", "", "Chef", "Inconnu"],
            ["Ina", "Sare", "ina@example.test", "", "Facilitateur communautaire"],
            ["Ina", "Bis", "INA@example.test", "", "Facilitateur communautaire"],
        ],
        assignments=[
            ["ina@example.test", "Borgou", "Nikki", "Bouca", "Gah"],   # Bouca is in Kalalè
            ["ina@example.test", "Borgou", "", "Nikki-Centre"],        # gap
            ["nobody@example.test", "Borgou", "Nikki"],
        ],
    )
    errors = errors_of(upload(staff_client, file))
    assert "Agents 2 E-mail: Un compte existe déjà avec cet e-mail." in errors
    assert "Agents 3 Nom: Obligatoire." in errors
    assert 'Agents 3 Rôle: « Chef » n’est pas un rôle de la liste.' in errors
    assert 'Agents 3 Groupe: « Inconnu » n’est pas un groupe existant.' in errors
    assert "Agents 5 E-mail: Aussi à la ligne 4 de cette feuille." in errors
    assert "Affectations 2 Arrondissement: « Bouca » n’est pas un(e) Arrondissement de Nikki." in errors
    assert any(error.startswith("Affectations 3 Commune: Vide") for error in errors)
    assert "Affectations 4 E-mail de l'agent: « nobody@example.test » n’est pas dans la feuille Agents." in errors
    assert CustomUser.objects.count() == 2  # staff user and the existing account
    assert "field_agent_import" not in staff_client.session


def test_a_facilitator_without_units_is_reported_on_the_assignments(staff_client, tree):
    errors = errors_of(upload(staff_client, fill(
        template(staff_client), [["Awa", "Bio", "awa@example.test", "", "Facilitateur technique"]]
    )))
    assert errors == [
        "Affectations None E-mail de l'agent: awa@example.test : Ajoutez au moins une unité dans une commune "
        "(la commune, un arrondissement ou un village), pour trouver sa commune et son superviseur."
    ]


def test_supervisor_is_required_only_when_the_commune_has_several_scs(staff_client, tree):
    make_sc(tree["Nikki"], "sc1@example.test", "Bio")
    second = make_sc(tree["Nikki"], "sc2@example.test", "Sabi")
    rows = [["awa@example.test", "Borgou", "Nikki", "Nikki-Centre", "Gah"]]
    errors = errors_of(upload(staff_client, fill(
        template(staff_client), [["Awa", "Bio", "awa@example.test", "", "Facilitateur communautaire"]], rows
    )))
    assert errors == ["Agents 2 Superviseur: Cette commune a plusieurs SC : choisissez le superviseur."]

    response = upload(staff_client, fill(template(staff_client), [[
        "Awa", "Bio", "awa@example.test", "", "Facilitateur communautaire", "", "Sabi SC (sc2@example.test)"
    ]], rows))
    assert errors_of(response) == []
    assert response.context["results"][0]["supervisor"] == f"{second} (sc2@example.test)"


def test_weak_password_keeps_the_preview_and_creates_nothing(staff_client, tree):
    upload(staff_client, fill(template(staff_client), [["Awa", "Bio", "awa@example.test", "", "Spécialiste national"]]))
    response = staff_client.post(CONFIRM, {"password1": "123", "password2": "123"})
    assert response.status_code == 200
    assert response.context["password_form"].errors
    assert response.context["results"]
    assert not CustomUser.objects.filter(email="awa@example.test").exists()


def test_everything_is_checked_again_at_creation(staff_client, tree):
    file = fill(template(staff_client), [
        ["Awa", "Bio", "awa@example.test", "", "Spécialiste national"],
        ["Ali", "Bio", "ali@example.test", "", "Spécialiste national"],
    ])
    assert errors_of(upload(staff_client, file)) == []
    CustomUser.objects.create_user(email="ali@example.test", password="x")  # created meanwhile
    response = staff_client.post(CONFIRM, {"password1": PASSWORD, "password2": PASSWORD})
    assert errors_of(response) == ["Agents 3 E-mail: Un compte existe déjà avec cet e-mail."]
    assert not CustomUser.objects.filter(email="awa@example.test").exists()


def test_confirm_without_a_checked_file_goes_back_to_the_upload(staff_client, tree):
    response = staff_client.post(CONFIRM, {"password1": PASSWORD, "password2": PASSWORD})
    assert response.status_code == 302 and response.url == PAGE


def test_a_file_that_is_not_the_template_is_refused(staff_client, tree):
    response = upload(staff_client, SimpleUploadedFile("agents.xlsx", b"not a spreadsheet"))
    assert errors_of(response) == [
        " None : Ce fichier ne peut pas être lu. Envoyez le modèle .xlsx, enregistré depuis Excel ou LibreOffice."
    ]
    response = upload(staff_client, SimpleUploadedFile("agents.csv", b"a,b"))
    assert response.context["file_form"].errors


def test_renamed_columns_are_reported(staff_client, tree):
    workbook = template(staff_client)
    workbook["Agents"]["E1"] = "Fonction"
    errors = errors_of(upload(staff_client, fill(workbook, [["Awa", "Bio", "awa@example.test"]])))
    assert errors and errors[0].startswith("Agents 1 Fonction: La colonne « Fonction » devrait être « Rôle »")
