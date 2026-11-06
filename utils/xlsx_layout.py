"""Layout helpers for the Excel templates people fill in (agent and unit imports)."""
from math import ceil

from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

LINE_HEIGHT = 15


def wrap_column(sheet, letter, width, first_row=1):
    """Wraps the text of a column and sets each row's height to show all of it: Excel does not
    resize the rows of a file written by openpyxl, so wrapped text would show its first line only."""
    sheet.column_dimensions[letter].width = width
    for row in range(first_row, sheet.max_row + 1):
        cell = sheet[f"{letter}{row}"]
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        text = str(cell.value or "")
        # A character is a little narrower than the width unit on average: this errs towards room.
        lines = sum(max(1, ceil(len(part) / width)) for part in text.split("\n"))
        sheet.row_dimensions[row].height = LINE_HEIGHT * lines


def fit_columns(sheet, columns, minimum=12, maximum=45):
    """Sets each column's width to its longest value. ``columns``: ``{column number: [values]}``,
    the header included."""
    for col, values in columns.items():
        longest = max((len(str(value)) for value in values if value is not None), default=0)
        sheet.column_dimensions[get_column_letter(col)].width = min(maximum, max(minimum, longest + 3))
