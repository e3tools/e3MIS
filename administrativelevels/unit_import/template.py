"""The Excel template, built from the database on each download: one column per level and the
current tree already filled in, one row per unit at the bottom of its branch (a village, or a unit
with nothing under it yet), so new units are added as rows below. Doubles as an export of the tree.
"""
from io import BytesIO

from django.utils import timezone
from django.utils.translation import gettext as _
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from administrativelevels.models import RURAL, URBAN, AdministrativeLevel, AdministrativeUnit
from administrativelevels.unit_import.importer import zone_level
from administrativelevels.unit_import.sheets import (
    INSTRUCTIONS_SHEET, MAX_ROWS, RURAL_LABEL, UNITS_SHEET, URBAN_LABEL, ZONE_HEADER,
)
from utils.xlsx_layout import fit_columns, wrap_column

HEADER_FONT = Font(bold=True)
HEADER_FILL = PatternFill("solid", fgColor="DDEBF7")
ZONE_FILL = PatternFill("solid", fgColor="E2EFDA")


def tree_rows():
    """``[(names from the top), zone]`` for every unit with no children, sorted by path."""
    units = {
        pk: (name, parent_id, level_id, zone)
        for pk, name, parent_id, level_id, zone in AdministrativeUnit.objects.values_list(
            "pk", "name", "parent_id", "level_id", "zone",
        )
    }
    parents = {parent_id for _name, parent_id, _level, _zone in units.values()}
    paths = {}

    def path(pk):
        if pk not in paths:
            name, parent_id = units[pk][:2]
            # A broken tree (parent missing) is cut there rather than failing the download.
            paths[pk] = (path(parent_id) if parent_id in units else []) + [name]
        return paths[pk]

    village_level = zone_level()
    labels = {URBAN: str(URBAN_LABEL), RURAL: str(RURAL_LABEL)}
    rows = [
        (path(pk), labels.get(zone, "") if village_level and level_id == village_level.pk else "")
        for pk, (_name, _parent, level_id, zone) in units.items()
        if pk not in parents
    ]
    return sorted(rows, key=lambda row: [name.casefold() for name in row[0]])


def build_template():
    """The template as ``bytes``."""
    workbook = Workbook()
    instructions = workbook.active
    instructions.title = str(INSTRUCTIONS_SHEET)
    units = workbook.create_sheet(str(UNITS_SHEET))
    levels = list(AdministrativeLevel.objects.order_by("order"))
    _fill_units(units, levels)
    _fill_instructions(instructions, levels)
    workbook.active = 1

    out = BytesIO()
    workbook.save(out)
    return out.getvalue()


def _fill_units(sheet, levels):
    headers = [level.name for level in levels] + [str(ZONE_HEADER)]
    for col, header in enumerate(headers, start=1):
        cell = sheet.cell(row=1, column=col, value=header)
        cell.font = HEADER_FONT
        cell.fill = ZONE_FILL if col == len(headers) else HEADER_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    sheet.freeze_panes = "A2"

    rows = tree_rows()
    for number, (path, zone) in enumerate(rows, start=2):
        for col, name in enumerate(path, start=1):
            sheet.cell(row=number, column=col, value=name)
        if zone:
            sheet.cell(row=number, column=len(headers), value=zone)

    zone_letter = get_column_letter(len(headers))
    validation = DataValidation(
        type="list", formula1=f'"{URBAN_LABEL},{RURAL_LABEL}"', allow_blank=True, showErrorMessage=True,
    )
    validation.errorTitle = _("Value not in the list")
    validation.error = _("Pick a value from the drop-down list.")
    sheet.add_data_validation(validation)
    validation.add(f"{zone_letter}2:{zone_letter}{MAX_ROWS + 1}")

    columns = {col: [level.name] for col, level in enumerate(levels, start=1)}
    for path, _zone in rows:
        for col, name in enumerate(path, start=1):
            columns.setdefault(col, []).append(name)
    fit_columns(sheet, columns, minimum=16)
    sheet.column_dimensions[zone_letter].width = 14


def _fill_instructions(sheet, levels):
    village_level = zone_level()
    lines = [
        (_("Add administrative units from this file"), True),
        (_("Generated on %(date)s with the current units already filled in. Download a new one if they "
           "changed.") % {"date": timezone.localtime().strftime("%d/%m/%Y %H:%M")}, False),
        ("", False),
        (_("Fill it in with Microsoft Excel or LibreOffice Calc only: Google Sheets and Numbers do not keep "
           "the drop-down lists."), True),
        (_("Do not rename the sheets or the columns, and do not add columns."), False),
        ("", False),
        (_("Units sheet: one column per level (%(levels)s), one row per unit at the bottom of its branch.")
         % {"levels": " → ".join(level.name for level in levels)}, True),
        (_("To add units, add rows below and write the full path, from the first level down to the new "
           "unit. Units that already exist are recognised (case and extra spaces do not count) and kept as "
           "they are; only the missing ones are created."), False),
        (_("A row can stop before the last level, for a unit with nothing under it yet. Fill the columns "
           "from left to right, without gaps."), False),
        (_("The import only adds: it never renames or deletes a unit. Deleting the rows of existing units "
           "changes nothing; rename or delete units on the administrative units page."), False),
        ("", False),
        (_("Zone column (optional): Urban or Rural, picked from the list."), True),
        (_("It sets the check-in radius of the worksites in the village (urban: smaller radius, rural: "
           "larger; set in the programme configuration). Only for units of the %(level)s level, on the "
           "row of that unit.") % {"level": village_level.name if village_level else "-"}, False),
        (_("A zone that differs from the current one replaces it, and the radius of the village's "
           "worksites whose position is not confirmed yet follows. An empty cell leaves the zone as it "
           "is."), False),
        ("", False),
        (_("Upload the file on the import page, at most %(max)s rows. Nothing is created until every row is "
           "correct: the page lists the errors with their row and column, then shows what will be created "
           "before you confirm.") % {"max": MAX_ROWS}, False),
    ]
    for row, (text, bold) in enumerate(lines, start=1):
        cell = sheet.cell(row=row, column=1, value=text)
        if bold:
            cell.font = HEADER_FONT
    wrap_column(sheet, "A", 100)
