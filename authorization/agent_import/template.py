"""The Excel template, built from the database on each download (new groups, units and SCs appear
at once).

Sheets: Instructions, Agents (one row per agent), Assignments (one row per agent and unit, levels
picked left to right) and the hidden Lists sheet behind the drop-down lists.

Each level's list holds the children of the units picked to its left. Unit names are only unique
under their parent (and some carry accents or apostrophes, which rules out named ranges), so Lists
keys children by their parent's path, the names from the top joined by "|", sorted by that key, with
an index of where each parent's children start and how many there are; the list reads it with
OFFSET/VLOOKUP. This works in Excel and LibreOffice, not in Google Sheets (no formula as a list
source).
"""
from io import BytesIO

from django.contrib.auth.models import Group
from django.utils import timezone
from django.utils.translation import gettext as _
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from administrativelevels.models import AdministrativeLevel, AdministrativeUnit
from authorization.agent_import.sheets import (
    AGENT_COLUMNS, AGENT_EMAIL_HEADER, AGENTS_SHEET, ASSIGNMENT_ROWS, ASSIGNMENTS_SHEET, INSTRUCTIONS_SHEET,
    LISTS_SHEET, MAX_AGENTS,
)
from authorization.infrastructure.forms.create_field_agent_form import FIELD_AGENT_ROLES
from authorization.models import CustomUser, Role

PATH_SEPARATOR = "|"
HEADER_FONT = Font(bold=True)
HEADER_FILL = PatternFill("solid", fgColor="DDEBF7")
REQUIRED_FILL = PatternFill("solid", fgColor="FCE4D6")

# Columns of the Lists sheet.
ROLES_COL, GROUPS_COL, SUPERVISORS_COL, ROOTS_COL = "A", "B", "C", "D"
PARENT_COL, CHILD_COL = "F", "G"
INDEX_KEY_COL, INDEX_START_COL, INDEX_COUNT_COL = "I", "J", "K"


def supervisor_label(user):
    return f"{user} ({user.email})"


def unit_paths():
    """``{unit id: [names from the top down to the unit]}`` and ``{parent id: [child names]}``."""
    units = {
        pk: (name, parent_id)
        for pk, name, parent_id in AdministrativeUnit.objects.values_list("pk", "name", "parent_id")
    }
    paths, children = {}, {}

    def path(pk):
        if pk not in paths:
            name, parent_id = units[pk]
            # A broken tree (parent missing) is cut there rather than failing the download.
            paths[pk] = (path(parent_id) if parent_id in units else []) + [name]
        return paths[pk]

    for pk, (name, parent_id) in units.items():
        path(pk)
        children.setdefault(parent_id, []).append(name)
    return paths, children


def build_template():
    """The template as ``bytes``."""
    workbook = Workbook()
    instructions = workbook.active
    instructions.title = str(INSTRUCTIONS_SHEET)
    agents = workbook.create_sheet(str(AGENTS_SHEET))
    assignments = workbook.create_sheet(str(ASSIGNMENTS_SHEET))
    lists = workbook.create_sheet(LISTS_SHEET)
    lists.sheet_state = "hidden"

    levels = list(AdministrativeLevel.objects.order_by("order"))
    ranges = _fill_lists(lists)
    _fill_agents(agents, ranges)
    _fill_assignments(assignments, levels, ranges)
    _fill_instructions(instructions, levels)

    out = BytesIO()
    workbook.save(out)
    return out.getvalue()


def _column(sheet, letter, values, start=2):
    """Writes ``values`` down a column of Lists; returns the absolute range, or None when empty."""
    for offset, value in enumerate(values):
        sheet[f"{letter}{start + offset}"] = value
    if not values:
        return None
    return f"{LISTS_SHEET}!${letter}${start}:${letter}${start + len(values) - 1}"


def _fill_lists(sheet):
    sheet["A1"], sheet["B1"], sheet["C1"], sheet["D1"] = "roles", "groups", "supervisors", "roots"
    scs = CustomUser.objects.filter(role=Role.SC, is_active=True).order_by("full_name", "email")
    paths, children = unit_paths()
    ranges = {
        "roles": _column(sheet, ROLES_COL, [role.label for role in FIELD_AGENT_ROLES]),
        "groups": _column(sheet, GROUPS_COL, list(Group.objects.order_by("name").values_list("name", flat=True))),
        "supervisors": _column(sheet, SUPERVISORS_COL, [supervisor_label(sc) for sc in scs]),
        "roots": _column(sheet, ROOTS_COL, sorted(children.get(None, []), key=str.casefold)),
    }

    # Children by parent path, and where each parent's block starts.
    sheet[f"{PARENT_COL}1"], sheet[f"{CHILD_COL}1"] = "parent", "child"
    sheet[f"{INDEX_KEY_COL}1"], sheet[f"{INDEX_START_COL}1"], sheet[f"{INDEX_COUNT_COL}1"] = "parent", "start", "count"
    blocks = sorted(
        (PATH_SEPARATOR.join(paths[parent_id]), sorted(names, key=str.casefold))
        for parent_id, names in children.items()
        if parent_id is not None and parent_id in paths
    )
    row = 2
    for index, (key, names) in enumerate(blocks, start=2):
        sheet[f"{INDEX_KEY_COL}{index}"] = key
        sheet[f"{INDEX_START_COL}{index}"] = row
        sheet[f"{INDEX_COUNT_COL}{index}"] = len(names)
        for name in names:
            sheet[f"{PARENT_COL}{row}"] = key
            sheet[f"{CHILD_COL}{row}"] = name
            row += 1
    return ranges


def _header(sheet, headers, required=()):
    for col, header in enumerate(headers, start=1):
        cell = sheet.cell(row=1, column=col, value=header)
        cell.font = HEADER_FONT
        cell.fill = REQUIRED_FILL if col in required else HEADER_FILL
        sheet.column_dimensions[get_column_letter(col)].width = max(18, len(header) + 4)
    sheet.freeze_panes = "A2"


def _list_validation(sheet, formula, cells, prompt=None):
    validation = DataValidation(type="list", formula1=formula, allow_blank=True, showErrorMessage=True)
    validation.errorTitle = _("Value not in the list")
    validation.error = _("Pick a value from the drop-down list.")
    if prompt:
        validation.promptTitle, validation.prompt, validation.showInputMessage = "", prompt, True
    sheet.add_data_validation(validation)
    validation.add(cells)


def _fill_agents(sheet, ranges):
    headers = [str(header) for _key, header, _required in AGENT_COLUMNS]
    required = {col for col, (_key, _header, req) in enumerate(AGENT_COLUMNS, start=1) if req}
    _header(sheet, headers, required)
    last = MAX_AGENTS + 1
    for col, (key, _header_text, _required) in enumerate(AGENT_COLUMNS, start=1):
        letter = get_column_letter(col)
        if key in ("email", "phone_number"):
            # Text, so a phone number keeps its leading zeros and "+".
            for row in range(2, last + 1):
                sheet[f"{letter}{row}"].number_format = "@"
        source = {"role": "roles", "group": "groups", "supervisor": "supervisors"}.get(key)
        if source and ranges[source]:
            prompt = _("Only when the commune has several SCs.") if key == "supervisor" else None
            _list_validation(sheet, ranges[source], f"{letter}2:{letter}{last}", prompt)
    sheet.column_dimensions["C"].width = 32
    sheet.column_dimensions["E"].width = 30
    sheet.column_dimensions["G"].width = 40


def _fill_assignments(sheet, levels, ranges):
    _header(sheet, [str(AGENT_EMAIL_HEADER)] + [level.name for level in levels], required={1})
    sheet.column_dimensions["A"].width = 32
    last = ASSIGNMENT_ROWS + 1
    _list_validation(
        sheet, f"'{AGENTS_SHEET}'!$C$2:$C${MAX_AGENTS + 1}", f"A2:A{last}",
        _("An email from the Agents sheet."),
    )
    for index, _level in enumerate(levels):
        letter = get_column_letter(index + 2)
        sheet.column_dimensions[letter].width = 24
        if index == 0:
            if ranges["roots"]:
                _list_validation(sheet, ranges["roots"], f"{letter}2:{letter}{last}")
            continue
        # The path of the units to the left, e.g. $B2&"|"&$C2 (relative row: Excel moves it down).
        key = f'&"{PATH_SEPARATOR}"&'.join(f"${get_column_letter(col)}2" for col in range(2, index + 2))
        index_range = f"{LISTS_SHEET}!${INDEX_KEY_COL}:${INDEX_COUNT_COL}"
        formula = (
            f"OFFSET({LISTS_SHEET}!${CHILD_COL}$1,VLOOKUP({key},{index_range},2,0)-1,0,"
            f"VLOOKUP({key},{index_range},3,0),1)"
        )
        _list_validation(sheet, formula, f"{letter}2:{letter}{last}")


def _fill_instructions(sheet, levels):
    level_names = " → ".join(level.name for level in levels)
    lines = [
        (_("Create field agents from this file"), True),
        (_("Generated on %(date)s from the current data (groups, units, supervisors). Download a new one if "
           "they changed.") % {"date": timezone.localtime().strftime("%d/%m/%Y %H:%M")}, False),
        ("", False),
        (_("Fill it in with Microsoft Excel or LibreOffice Calc only: Google Sheets and Numbers do not keep "
           "the drop-down lists."), True),
        (_("Do not rename the sheets or the columns, and do not add columns."), False),
        ("", False),
        (_("Agents sheet: one row per agent (at most %(max)s).") % {"max": MAX_AGENTS}, True),
        (_("First name, last name and email are required (orange columns). The email is the sign-in name and "
           "must not belong to an existing account."), False),
        (_("Role: pick it from the list. It can stay empty when the group has a default role."), False),
        (_("Group: one group per agent; it decides which forms the agent sees."), False),
        (_("Supervisor: leave it empty. The SC of the agent's commune is found automatically; pick one only "
           "when that commune has several SCs. An SC created in this file can be typed by their email."), False),
        ("", False),
        (_("Assignments sheet: one row per agent and administrative unit."), True),
        (_("Pick the agent's email, then the units from left to right (%(levels)s); each list only shows "
           "the units inside the one on its left. Stop at the level you need:") % {"levels": level_names}, False),
        (_("- community facilitator: one row per village;"), False),
        (_("- technical facilitator and communal supervisor: their commune;"), False),
        (_("- regional specialist: their department; national specialist: no row."), False),
        (_("The commune with most of an agent's units is their commune, and gives their supervisor."), False),
        ("", False),
        (_("Upload the file on the import page. Nothing is created until every row is correct: the page lists "
           "the errors with their sheet, row and column. Then it asks for one password, used by all the new "
           "accounts."), False),
    ]
    for row, (text, bold) in enumerate(lines, start=1):
        cell = sheet.cell(row=row, column=1, value=text)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        if bold:
            cell.font = HEADER_FONT
    sheet.column_dimensions["A"].width = 120
