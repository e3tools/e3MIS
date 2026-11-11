"""Reads an uploaded agent file into plain data (JSON-safe: the page keeps it in the session between
the check and the password step).

One sheet, one row per agent and unit. A row with agent details starts an agent; the rows below
with the agent cells left empty add units to that agent. Repeating the details of the agent above is
accepted when they are the same (a differing value is an error, it is probably another agent).

Only the layout is checked here: sheet, headers, how the rows group into agents, empty or
out-of-order level cells. Names are matched to roles, groups and units by importer.py, against the
database as it is at that moment.
"""
import re
from zipfile import BadZipFile

from django.utils.translation import gettext as _
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from administrativelevels.models import AdministrativeLevel
from authorization.agent_import.sheets import (
    AGENT_COLUMNS, AGENTS_SHEET, ASSIGNMENTS_SHEET, MAX_AGENTS, in_all_languages,
)
from authorization.infrastructure.forms.create_field_agent_form import FIELD_AGENT_ROLES

AGENT_KEYS = [key for key, _header, _required in AGENT_COLUMNS]
HEADERS = {key: header for key, header, _required in AGENT_COLUMNS}


def problem(sheet, row, column, message):
    """One error, shown as "sheet, row N, column: message" (row and column may be empty)."""
    return {
        "sheet": str(sheet) if sheet else "", "row": row, "column": str(column) if column else "", "message": message,
    }


def sort_problems(errors):
    """Problems about the whole file first, then by sheet and row."""
    return sorted(errors, key=lambda error: (error["row"] is not None, error["sheet"] != str(AGENTS_SHEET),
                                             error["sheet"], error["row"] or 0))


def text(value):
    """A cell as trimmed text: a phone typed as a number keeps no ".0"."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def role_code(value):
    """The role code for a label or code from the file; "" when empty; None when unknown."""
    if not value:
        return ""
    folded = value.casefold()
    return next((role.value for role in FIELD_AGENT_ROLES if folded in (role.value, role.label.casefold())), None)


def supervisor_email(value):
    """The email in "Name (email)" as the list shows SCs, or the value itself."""
    if value.endswith(")") and "(" in value:
        return value[value.rindex("(") + 1:-1].strip()
    return value


def _same_text(value):
    return " ".join(value.split()).casefold()


# How two values of a column are compared when an agent's details are repeated on a later row:
# "0197000001" and "01 97 00 00 01" are one phone, "fc" and "Facilitateur communautaire" one role.
COMPARE = {
    "phone_number": lambda value: re.sub(r"\D", "", value),
    "role": lambda value: role_code(value) or _same_text(value),
    "supervisor": lambda value: supervisor_email(value).casefold(),
}


def _key(column, value):
    return COMPARE.get(column, _same_text)(value)


def _sheet(workbook, name):
    names = in_all_languages(name)
    return next((sheet for sheet in workbook.worksheets if sheet.title.casefold() in names), None)


def _rows(sheet, width):
    """``(row number, [cells as text])`` for every row below the header that is not empty. A merged
    block of cells (e.g. an agent's name over their rows) counts as its value on each of its rows."""
    merged = {}
    for cells in sheet.merged_cells.ranges:
        value = sheet.cell(row=cells.min_row, column=cells.min_col).value
        for row in range(cells.min_row, cells.max_row + 1):
            for col in range(cells.min_col, cells.max_col + 1):
                merged[(row, col)] = value
    for number, values in enumerate(sheet.iter_rows(min_row=2, max_col=width, values_only=True), start=2):
        values = list(values) + [None] * (width - len(values))
        cells = [text(merged.get((number, col), value)) for col, value in enumerate(values, start=1)]
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
    """``(agents, errors)``. Each agent: ``row`` (their first row), the agent columns, and
    ``units``, a list of ``{"row": n, "path": [unit names from the top]}`` (``invalid_units`` when
    one of their rows is wrong). Agents come back with row errors too, so the names can be checked
    in the same pass; not when the layout itself is wrong."""
    try:
        # Not read-only: merged cells are only known to a fully loaded sheet.
        workbook = load_workbook(uploaded, data_only=True)
    except (BadZipFile, InvalidFileException, KeyError, OSError, ValueError):
        return [], [problem("", None, "", _(
            "This file cannot be read. Upload the .xlsx template, saved from Excel or LibreOffice."
        ))]
    try:
        return _read(workbook)
    finally:
        workbook.close()


def _read(workbook):
    if _sheet(workbook, ASSIGNMENTS_SHEET) is not None:
        return [], [problem("", None, "", _(
            "This is the former template, with a separate Assignments sheet. Download the new template from "
            "this page: each agent and their units now go on the Agents sheet."
        ))]
    sheet = _sheet(workbook, AGENTS_SHEET)
    if sheet is None:
        return [], [problem(AGENTS_SHEET, None, "", _(
            'The sheet "%(name)s" is missing: use the template from this page.'
        ) % {"name": AGENTS_SHEET})]

    errors = []
    levels = list(AdministrativeLevel.objects.order_by("order").values_list("name", flat=True))
    _check_headers(sheet, [header for _key, header, _required in AGENT_COLUMNS] + levels, errors)
    if errors:
        return [], errors

    title = sheet.title
    agents = []
    current, last_row = None, None

    def error(row, column, message):
        errors.append(problem(title, row, column, message))

    for number, cells in _rows(sheet, len(AGENT_KEYS) + len(levels)):
        details = dict(zip(AGENT_KEYS, cells))
        filled = {key: value for key, value in details.items() if value}
        names = cells[len(AGENT_KEYS):]
        follows = last_row is not None and number == last_row + 1
        last_row = number

        if not filled:
            # More units for the agent above.
            if current is None:
                error(number, HEADERS["first_name"], _(
                    "No agent above this row: fill in the agent's first name, last name and email on their "
                    "first row."
                ))
                continue
            if not follows:
                current["invalid_units"] = True
                error(number, HEADERS["first_name"], _(
                    "The row above is empty, so this row cannot be given to the agent of row %(row)s. Remove "
                    "the empty row, or fill in the agent if it is another one."
                ) % {"row": current["row"]})
                continue
        elif current is not None and _repeats(current, filled):
            # The details of the agent above, repeated: only allowed when they are the same.
            for key, value in filled.items():
                if _key(key, value) == _key(key, current[key]):
                    continue
                current["invalid_units"] = True
                if current[key]:
                    message = _(
                        'Differs from row %(row)s, the first row of this agent ("%(value)s"). On the rows of '
                        "their other units, leave the agent cells empty or repeat the same values; another "
                        "agent needs their own email."
                    ) % {"row": current["row"], "value": current[key]}
                else:
                    message = _(
                        "Empty on row %(row)s, the first row of this agent: fill in the agent's details on "
                        "their first row."
                    ) % {"row": current["row"]}
                error(number, HEADERS[key], message)
        else:
            # A new agent.
            current = dict(details, row=number, units=[])
            agents.append(current)
            if not details["email"]:
                current["invalid_units"] = True
                error(number, HEADERS["email"], _(
                    "Required. On the rows of an agent's other units, leave all the agent cells empty."
                ))
            for key, header, required in AGENT_COLUMNS:
                if required and key != "email" and not details[key]:
                    error(number, header, _("Required."))

        _add_unit(current, number, names, levels, error)

    if not agents:
        errors.append(problem(title, None, "", _("No agent: fill in at least one row.")))
    if len(agents) > MAX_AGENTS:
        errors.append(problem(title, None, "", _(
            "%(count)s agents: a file holds at most %(max)s. Split it into several files."
        ) % {"count": len(agents), "max": MAX_AGENTS}))
    return agents, errors


def _repeats(current, filled):
    """Whether a row's details repeat the agent above: the same email, or no email and every
    filled cell equal to that agent's."""
    if filled.get("email"):
        return filled["email"].casefold() == current["email"].casefold()
    return all(_key(key, value) == _key(key, current[key]) for key, value in filled.items())


def _add_unit(agent, number, names, levels, error):
    depth = next((i for i, name in enumerate(names) if not name), len(names))
    if any(names[depth:]):
        agent["invalid_units"] = True
        error(number, levels[depth], _(
            "Empty, while a level to its right is filled: pick the units from left to right."
        ))
    elif depth:
        agent["units"].append({"row": number, "path": names[:depth]})
