"""Reads an uploaded agent file into plain data (JSON-safe: the page keeps it in the session between
the check and the password step).

Only the layout is checked here: sheets, headers, empty or out-of-order cells. Names are matched to
roles, groups and units by importer.py, against the database as it is at that moment.
"""
from zipfile import BadZipFile

from django.utils.translation import gettext as _
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from administrativelevels.models import AdministrativeLevel
from authorization.agent_import.sheets import (
    AGENT_COLUMNS, AGENT_EMAIL_HEADER, AGENTS_SHEET, ASSIGNMENTS_SHEET, MAX_AGENTS, in_all_languages,
)


def problem(sheet, row, column, message):
    """One error, shown as "sheet, row N, column: message" (row and column may be empty)."""
    return {
        "sheet": str(sheet) if sheet else "", "row": row, "column": str(column) if column else "", "message": message,
    }


def sort_problems(errors):
    """Agents sheet first, then by sheet and row; problems about the whole file first."""
    return sorted(errors, key=lambda error: (error["row"] is not None, error["sheet"] != str(AGENTS_SHEET),
                                             error["sheet"], error["row"] or 0))


def text(value):
    """A cell as trimmed text: a phone typed as a number keeps no ".0"."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _sheet(workbook, name):
    names = in_all_languages(name)
    return next((sheet for sheet in workbook.worksheets if sheet.title.casefold() in names), None)


def _rows(sheet, width):
    """``(row number, [cells as text])`` for every row below the header that is not empty."""
    for number, values in enumerate(sheet.iter_rows(min_row=2, max_col=width, values_only=True), start=2):
        cells = [text(value) for value in values] + [""] * (width - len(values))
        if any(cells):
            yield number, cells


def _check_headers(sheet, expected, errors):
    """``expected`` holds lazy texts (any language accepted) or plain names (level names)."""
    found = [text(cell) for cell in next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), ())]
    for col, header in enumerate(expected):
        names = {header.casefold()} if isinstance(header, str) else in_all_languages(header)
        value = found[col] if col < len(found) else ""
        if value.casefold() not in names:
            errors.append(problem(sheet.title, 1, value or col + 1, _(
                'The column "%(found)s" should be "%(expected)s". Do not rename or move the columns; '
                'download a new template if the levels have changed.'
            ) % {"found": value, "expected": str(header)}))


def read_file(uploaded):
    """``(agents, errors)``. Each agent: ``row``, the Agents columns, and ``units``, a list of
    ``{"row": n, "path": [unit names from the top]}`` from the Assignments sheet (``invalid_units``
    when one of their rows there is wrong). Agents come back with row errors too, so the names can
    be checked in the same pass; not when the layout itself is wrong."""
    try:
        workbook = load_workbook(uploaded, read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, KeyError, OSError, ValueError):
        return [], [problem("", None, "", _(
            "This file cannot be read. Upload the .xlsx template, saved from Excel or LibreOffice."
        ))]
    try:
        return _read(workbook)
    finally:
        workbook.close()


def _read(workbook):
    errors = []
    agents_sheet, assignments_sheet = _sheet(workbook, AGENTS_SHEET), _sheet(workbook, ASSIGNMENTS_SHEET)
    for sheet, name in ((agents_sheet, AGENTS_SHEET), (assignments_sheet, ASSIGNMENTS_SHEET)):
        if sheet is None:
            errors.append(problem(name, None, "", _(
                'The sheet "%(name)s" is missing: use the template from this page.'
            ) % {"name": name}))
    if errors:
        return [], errors

    levels = list(AdministrativeLevel.objects.order_by("order").values_list("name", flat=True))
    _check_headers(agents_sheet, [header for _key, header, _required in AGENT_COLUMNS], errors)
    _check_headers(assignments_sheet, [AGENT_EMAIL_HEADER] + levels, errors)
    if errors:
        return [], errors

    keys = [key for key, _header, _required in AGENT_COLUMNS]
    agents = []
    for number, cells in _rows(agents_sheet, len(keys)):
        agent = dict(zip(keys, cells), row=number, units=[])
        for key, header, required in AGENT_COLUMNS:
            if required and not agent[key]:
                errors.append(problem(agents_sheet.title, number, header, _("Required.")))
        agents.append(agent)
    if not agents:
        errors.append(problem(agents_sheet.title, None, "", _("No agent: fill in at least one row.")))
    if len(agents) > MAX_AGENTS:
        errors.append(problem(agents_sheet.title, None, "", _(
            "%(count)s agents: a file holds at most %(max)s. Split it into several files."
        ) % {"count": len(agents), "max": MAX_AGENTS}))

    by_email = {}
    for agent in agents:
        if agent["email"]:
            by_email.setdefault(agent["email"].casefold(), agent)

    email_header = str(AGENT_EMAIL_HEADER)
    for number, cells in _rows(assignments_sheet, 1 + len(levels)):
        email, names = cells[0], cells[1:]
        if not email:
            errors.append(problem(assignments_sheet.title, number, email_header, _("Required.")))
            continue
        agent = by_email.get(email.casefold())
        if agent is None:
            errors.append(problem(assignments_sheet.title, number, email_header, _(
                '"%(email)s" is not in the Agents sheet.'
            ) % {"email": email}))
            continue
        depth = next((i for i, name in enumerate(names) if not name), len(names))
        if depth == 0:
            agent["invalid_units"] = True
            errors.append(problem(assignments_sheet.title, number, levels[0] if levels else "", _(
                "No unit: pick at least the first level."
            )))
            continue
        if any(names[depth:]):
            agent["invalid_units"] = True
            errors.append(problem(assignments_sheet.title, number, levels[depth], _(
                "Empty, while a level to its right is filled: pick the units from left to right."
            )))
            continue
        agent["units"].append({"row": number, "path": names[:depth]})
    return agents, errors
