"""Reads an uploaded unit file into plain data (JSON-safe: the page keeps it in the session between
the check and the confirmation). Only the layout is checked here; importer.py matches the names
against the tree.
"""
from zipfile import BadZipFile

from django.utils.translation import gettext as _
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from administrativelevels.models import RURAL, URBAN, AdministrativeLevel
from administrativelevels.unit_import.sheets import (
    MAX_ROWS, RURAL_LABEL, UNITS_SHEET, URBAN_LABEL, ZONE_HEADER, in_all_languages,
)


def problem(row, column, message):
    """One error, shown as "row N, column: message" (row and column may be empty)."""
    return {"row": row, "column": str(column) if column else "", "message": message}


def text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def zone_of(value):
    """``urban``, ``rural``, ``""`` for an empty cell, None when not understood (any language)."""
    value = value.casefold()
    if not value:
        return ""
    if value in in_all_languages(URBAN_LABEL) | {URBAN}:
        return URBAN
    if value in in_all_languages(RURAL_LABEL) | {RURAL}:
        return RURAL
    return None


def _header(sheet):
    return [text(cell) for cell in next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), ())]


def _units_sheet(workbook, levels):
    """The template's sheet; otherwise the first sheet whose columns are the levels (a file in the
    layout of sync_administrative_levels)."""
    names = in_all_languages(UNITS_SHEET)
    sheet = next((sheet for sheet in workbook.worksheets if sheet.title.casefold() in names), None)
    if sheet is not None:
        return sheet
    expected = [level.casefold() for level in levels]
    return next(
        (sheet for sheet in workbook.worksheets
         if [value.casefold() for value in _header(sheet)[:len(levels)]] == expected),
        None,
    )


def read_file(uploaded):
    """``(rows, errors)``. Each row: ``{"row": n, "path": [names from the top], "zone": ...}``."""
    try:
        workbook = load_workbook(uploaded, read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, KeyError, OSError, ValueError):
        return [], [problem(None, "", _(
            "This file cannot be read. Upload the .xlsx template, saved from Excel or LibreOffice."
        ))]
    try:
        return _read(workbook)
    finally:
        workbook.close()


def _read(workbook):
    levels = list(AdministrativeLevel.objects.order_by("order").values_list("name", flat=True))
    sheet = _units_sheet(workbook, levels)
    if sheet is None:
        return [], [problem(None, "", _(
            'The sheet "%(name)s" is missing: use the template from this page.'
        ) % {"name": UNITS_SHEET})]

    errors = []
    found = _header(sheet)
    for col, level in enumerate(levels):
        value = found[col] if col < len(found) else ""
        if value.casefold() != level.casefold():
            errors.append(problem(1, value or col + 1, _(
                'The column "%(found)s" should be "%(expected)s". Do not rename or move the columns; '
                'download a new template if the levels have changed.'
            ) % {"found": value, "expected": level}))
    extra = found[len(levels)] if len(found) > len(levels) else ""
    has_zone = extra.casefold() in in_all_languages(ZONE_HEADER)
    if extra and not has_zone:
        errors.append(problem(1, extra, _(
            'The column after the levels should be "%(expected)s" or nothing.'
        ) % {"expected": ZONE_HEADER}))
    if errors:
        return [], errors

    rows = []
    width = len(levels) + has_zone
    for number, values in enumerate(sheet.iter_rows(min_row=2, max_col=width, values_only=True), start=2):
        cells = [text(value) for value in values] + [""] * (width - len(values))
        if not any(cells):
            continue
        if len(rows) == MAX_ROWS:
            errors.append(problem(None, "", _(
                "More than %(max)s rows: split the file into several files."
            ) % {"max": MAX_ROWS}))
            break
        names = cells[:len(levels)]
        depth = next((i for i, name in enumerate(names) if not name), len(names))
        if depth == 0:
            errors.append(problem(number, levels[0], _("Required.")))
            continue
        if any(names[depth:]):
            errors.append(problem(number, levels[depth], _(
                "Empty, while a level to its right is filled: write the full path from the first level."
            )))
            continue
        zone = zone_of(cells[-1]) if has_zone else ""
        if zone is None:
            errors.append(problem(number, ZONE_HEADER, _(
                '"%(value)s" is not a zone: pick %(urban)s or %(rural)s.'
            ) % {"value": cells[-1], "urban": URBAN_LABEL, "rural": RURAL_LABEL}))
            continue
        rows.append({"row": number, "path": names[:depth], "zone": zone})
    if not rows and not errors:
        errors.append(problem(None, "", _("No unit: fill in at least one row.")))
    return rows, errors
