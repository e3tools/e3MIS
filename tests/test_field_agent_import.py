"""Field agents created in bulk from an Excel file (Nov 2026).

The template is built from the database (groups, units, SCs as drop-down lists, the units in a
cascade). One sheet, one row per agent and unit: the agent's details on their first row, empty on
the rows of their other units. The upload is checked with the field-agents page's own form, then a shared password is
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


AGENT_CELLS = 7  # first name … supervisor; the levels follow


def line(details=(), *units):
    """A row of the Agents sheet: the agent cells (padded), then the unit names from the top."""
    return list(details) + [""] * (AGENT_CELLS - len(details)) + list(units)


def fill(workbook, rows=(), start=2):
    """Writes rows below the headers (``None`` leaves a row empty); returns the file as an upload."""
    for row, values in enumerate(rows, start=start):
        for col, value in enumerate(values or [], start=1):
            workbook["Agents"].cell(row=row, column=col, value=value or None)
    return as_upload(workbook)


def as_upload(workbook):
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
    response = upload(staff_client, fill(template(staff_client), [line(["Awa", "Bio", "awa@example.test"])]))
    assert not CustomUser.objects.filter(email="awa@example.test").exists()
    assert "import stays closed" in response.content.decode() or "reste fermé" in response.content.decode()


# --- Template ----------------------------------------------------------------------------------

def test_template_lists_current_roles_groups_scs_and_units(staff_client, tree, fc_group):
    make_sc(tree["Nikki"], "sc.nikki@example.test", "Bio")
    workbook = template(staff_client)
    assert workbook.sheetnames == ["Instructions", "Agents", "Lists"]
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
    assert [c.value for c in workbook["Agents"][1]] == [
        "Prénom", "Nom", "E-mail", "Téléphone", "Rôle", "Groupe", "Superviseur",
        "Department", "Commune", "Arrondissement", "Village",
    ]


def test_instructions_show_a_worked_example_with_real_units(staff_client, tree):
    rows = [[cell.value for cell in row] for row in template(staff_client)["Instructions"].iter_rows()]
    header = next(index for index, row in enumerate(rows) if row[0] == "Prénom")
    example = rows[header + 1:]
    # First row: details and a village; second: same agent, details empty, another village nearby.
    assert example[0][:3] == ["Awa", "BIO", "awa.bio@example.org"]
    assert example[0][7:11] == ["Borgou", "Kalalè", "Bouca", "Gah"]
    assert example[1][:7] == [None] * 7 and example[1][7:11] == ["Borgou", "Kalalè", "Bouca", "Kalalè Sud"]
    sc = next(row for row in example if row[4] == "Superviseur communal")
    assert sc[7:11] == ["Borgou", "Kalalè", None, None]
    assert all(row[11] for row in example)  # each row explained


def test_template_cascade_reads_the_units_on_the_left(staff_client, tree):
    validations = template(staff_client)["Agents"].data_validations.dataValidation
    formulas = {str(v.sqref).split(":")[0]: v.formula1 for v in validations}
    assert formulas["H2"] == "Lists!$D$2:$D$2"
    assert formulas["J2"] == (
        'OFFSET(Lists!$G$1,VLOOKUP($H2&"|"&$I2,Lists!$I:$K,2,0)-1,0,VLOOKUP($H2&"|"&$I2,Lists!$I:$K,3,0),1)'
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
    file = fill(template(staff_client), [
        line(["Awa", "Bio", "awa@example.test", "22997000001", "", "Community facilitator"],
             "Borgou", "Nikki", "Nikki-Centre", "Gah"),
        line([], "Borgou", "Nikki", "Nikki-Centre", "Nikki Sud"),
        line(["Koffi", "Sare", "koffi@example.test", "", "Superviseur communal"], "Borgou", "Nikki"),
    ])
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
    file = fill(template(staff_client), [
        line(["Koffi", "Sare", "koffi@example.test", "", "Superviseur communal"], "Borgou", "Kalalè"),
    ])
    upload(staff_client, file)
    staff_client.post(CONFIRM, {"password1": PASSWORD, "password2": PASSWORD})
    waiting.refresh_from_db()
    assert waiting.supervisor.email == "koffi@example.test"


def test_errors_name_the_row_and_column_and_nothing_is_created(staff_client, tree, fc_group):
    CustomUser.objects.create_user(email="Taken@Example.test", password="x")
    file = fill(template(staff_client), [
        line(["Awa", "Bio", "taken@example.test", "", "Facilitateur communautaire"], "Borgou", "Nikki"),
        line(["Ali", "", "ali@example.test", "", "Chef", "Inconnu"], "Borgou", "Nikki"),
        line(["Ina", "Sare", "ina@example.test", "", "Facilitateur communautaire"],
             "Borgou", "Nikki", "Bouca", "Gah"),                                # Bouca is in Kalalè
        line([], "Borgou", "", "Nikki-Centre"),                                 # gap
    ])
    errors = errors_of(upload(staff_client, file))
    assert errors == [
        "Agents 2 E-mail: Un compte existe déjà avec cet e-mail.",
        "Agents 3 Nom: Obligatoire.",
        "Agents 3 Rôle: « Chef » n’est pas un rôle de la liste.",
        "Agents 3 Groupe: « Inconnu » n’est pas un groupe existant.",
        "Agents 4 Arrondissement: « Bouca » n’est pas un(e) Arrondissement de Nikki.",
        "Agents 5 Commune: Vide, alors qu’un niveau à sa droite est rempli : choisissez les unités de gauche "
        "à droite.",
    ]
    assert CustomUser.objects.count() == 2  # staff user and the existing account
    assert "field_agent_import" not in staff_client.session


def test_a_facilitator_without_units_is_reported_on_their_row(staff_client, tree):
    errors = errors_of(upload(staff_client, fill(
        template(staff_client), [line(["Awa", "Bio", "awa@example.test", "", "Facilitateur technique"])]
    )))
    assert errors == [
        "Agents 2 Department: Ajoutez au moins une unité dans une commune "
        "(la commune, un arrondissement ou un village), pour trouver sa commune et son superviseur."
    ]


def test_supervisor_is_required_only_when_the_commune_has_several_scs(staff_client, tree):
    make_sc(tree["Nikki"], "sc1@example.test", "Bio")
    second = make_sc(tree["Nikki"], "sc2@example.test", "Sabi")
    units = ["Borgou", "Nikki", "Nikki-Centre", "Gah"]
    errors = errors_of(upload(staff_client, fill(
        template(staff_client), [line(["Awa", "Bio", "awa@example.test", "", "Facilitateur communautaire"], *units)]
    )))
    assert errors == ["Agents 2 Superviseur: Cette commune a plusieurs SC : choisissez le superviseur."]

    response = upload(staff_client, fill(template(staff_client), [line([
        "Awa", "Bio", "awa@example.test", "", "Facilitateur communautaire", "", "Sabi SC (sc2@example.test)"
    ], *units)]))
    assert errors_of(response) == []
    assert response.context["results"][0]["supervisor"] == f"{second} (sc2@example.test)"


def test_weak_password_keeps_the_preview_and_creates_nothing(staff_client, tree):
    upload(staff_client, fill(template(staff_client), [
        line(["Awa", "Bio", "awa@example.test", "", "Spécialiste national"]),
    ]))
    response = staff_client.post(CONFIRM, {"password1": "123", "password2": "123"})
    assert response.status_code == 200
    assert response.context["password_form"].errors
    assert response.context["results"]
    assert not CustomUser.objects.filter(email="awa@example.test").exists()


def test_everything_is_checked_again_at_creation(staff_client, tree):
    file = fill(template(staff_client), [
        line(["Awa", "Bio", "awa@example.test", "", "Spécialiste national"]),
        line(["Ali", "Bio", "ali@example.test", "", "Spécialiste national"]),
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
    errors = errors_of(upload(staff_client, fill(workbook, [line(["Awa", "Bio", "awa@example.test"])])))
    assert errors and errors[0].startswith("Agents 1 Fonction: La colonne « Fonction » devrait être « Rôle »")


# --- How rows group into agents ----------------------------------------------------------------

AWA = ["Awa", "Bio", "awa@example.test", "0197000001", "Facilitateur communautaire"]


def test_repeating_the_same_details_is_accepted(staff_client, tree):
    """Written differently (spaces, case, role code) but the same values: still the agent above."""
    response = upload(staff_client, fill(template(staff_client), [
        line(AWA, "Borgou", "Nikki", "Nikki-Centre", "Gah"),
        line(["awa", "BIO", "AWA@example.test", "01 97 00 00 01", "fc"],
             "Borgou", "Nikki", "Nikki-Centre", "Nikki Sud"),
        line(["", "", "awa@example.test"], "Borgou", "Kalalè", "Bouca", "Gah"),
        line(["Awa", "Bio"], "Borgou", "Kalalè", "Bouca", "Kalalè Sud"),
    ]))
    assert errors_of(response) == []
    assert len(response.context["results"][0]["units"]) == 4


def test_repeated_details_that_differ_are_reported(staff_client, tree):
    errors = errors_of(upload(staff_client, fill(template(staff_client), [
        line(["Awa", "Bio", "awa@example.test"], "Borgou", "Nikki", "Nikki-Centre", "Gah"),
        line(["Awa", "Bio", "awa@example.test", "0197000002"], "Borgou", "Nikki", "Nikki-Centre", "Nikki Sud"),
        line(["Awa", "Sare", "awa@example.test"], "Borgou", "Kalalè"),
    ])))
    assert errors == [
        "Agents 3 Téléphone: Vide à la ligne 2, la première ligne de cet agent : renseignez l’agent sur sa "
        "première ligne.",
        "Agents 4 Nom: Diffère de la ligne 2, la première ligne de cet agent (« Bio »). Sur les lignes de ses "
        "autres unités, laissez les cellules de l’agent vides ou répétez les mêmes valeurs ; un autre agent "
        "a besoin de son propre e-mail.",
    ]


def test_details_without_an_email_are_a_new_agent_missing_it(staff_client, tree):
    """Another name and no email: not the agent above."""
    errors = errors_of(upload(staff_client, fill(template(staff_client), [
        line(AWA, "Borgou", "Nikki", "Nikki-Centre", "Gah"),
        line(["Ali", "Bio"], "Borgou", "Nikki", "Nikki-Centre", "Nikki Sud"),
    ])))
    assert errors == [
        "Agents 3 E-mail: Obligatoire. Sur les lignes des autres unités d’un agent, laissez toutes les "
        "cellules de l’agent vides."
    ]


def test_unit_rows_need_their_agent_right_above(staff_client, tree):
    errors = errors_of(upload(staff_client, fill(template(staff_client), [
        line([], "Borgou", "Nikki"),
        line(AWA, "Borgou", "Nikki", "Nikki-Centre", "Gah"),
        None,
        line([], "Borgou", "Nikki", "Nikki-Centre", "Nikki Sud"),
    ])))
    assert errors == [
        "Agents 2 Prénom: Aucun agent au-dessus de cette ligne : renseignez le prénom, le nom et l’e-mail de "
        "l’agent sur sa première ligne.",
        "Agents 5 Prénom: La ligne au-dessus est vide : cette ligne ne peut pas être attribuée à l’agent de la "
        "ligne 3. Supprimez la ligne vide, ou renseignez l’agent s’il s’agit d’un autre.",
    ]


def test_an_agent_split_in_two_blocks_is_reported(staff_client, tree):
    errors = errors_of(upload(staff_client, fill(template(staff_client), [
        line(AWA, "Borgou", "Nikki", "Nikki-Centre", "Gah"),
        line(["Koffi", "Sare", "koffi@example.test", "", "Spécialiste national"]),
        line(AWA, "Borgou", "Nikki", "Nikki-Centre", "Nikki Sud"),
    ])))
    assert errors == [
        "Agents 4 E-mail: Cet agent commence déjà à la ligne 2 : mettez toutes ses unités dans un seul bloc "
        "sous cette ligne (cellules de l’agent vides), ou donnez à cet autre agent son propre e-mail."
    ]


def test_a_unit_given_twice_or_inside_another_is_reported(staff_client, tree):
    errors = errors_of(upload(staff_client, fill(template(staff_client), [
        line(AWA, "Borgou", "Nikki", "Nikki-Centre", "Gah"),
        line([], "Borgou", "Nikki", "Nikki-Centre", "Gah"),       # copied down, village not changed
        line([], "Borgou", "Nikki"),                              # contains Gah
        line([], "Borgou", "Kalalè"),
        line([], "Borgou", "Kalalè", "Bouca", "Gah"),             # inside Kalalè
    ])))
    assert errors == [
        "Agents 3 Village: Même unité qu’à la ligne 2 : cet agent ne l’a qu’une fois.",
        "Agents 4 Commune: « Nikki » contient Gah, déjà donné(e) à la ligne 2 : gardez une seule des deux lignes.",
        "Agents 6 Village: « Gah » est dans Kalalè, déjà donné(e) à la ligne 5 : gardez une seule des deux lignes.",
    ]


def test_merged_cells_count_on_each_of_their_rows(staff_client, tree):
    """An agent's name merged over their rows, or a commune merged over its villages."""
    workbook = template(staff_client)
    sheet = workbook["Agents"]
    for row, values in enumerate([
        line(AWA, "Borgou", "Nikki", "Nikki-Centre", "Gah"),
        line([], "", "", "", "Nikki Sud"),
    ], start=2):
        for col, value in enumerate(values, start=1):
            sheet.cell(row=row, column=col, value=value or None)
    sheet.merge_cells("A2:A3")
    for letter in "HIJ":
        sheet.merge_cells(f"{letter}2:{letter}3")
    response = upload(staff_client, as_upload(workbook))
    assert errors_of(response) == []
    assert sorted(response.context["results"][0]["units"]) == ["Gah", "Nikki Sud"]


def test_the_former_two_sheet_template_is_refused(staff_client, tree):
    workbook = template(staff_client)
    workbook.create_sheet("Affectations")
    errors = errors_of(upload(staff_client, fill(workbook, [line(AWA, "Borgou", "Nikki")])))
    assert errors == [
        " None : C’est l’ancien modèle, avec une feuille Affectations à part. Téléchargez le nouveau modèle "
        "depuis cette page : chaque agent et ses unités vont maintenant sur la feuille Agents."
    ]
