"""Files made from an event: the signed list (PDF with the signatures, Excel without), a blank list to
print for people who sign on paper, and the QR code."""
import os
from io import BytesIO

import segno
from django.utils import formats, timezone
from django.utils.translation import gettext as _
from fpdf import FPDF
from fpdf.fonts import FontFace
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from events.attendance import gender_counts, gender_summary
from utils.xlsx_layout import fit_columns

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
HEADER_FILL = (221, 235, 247)
# Relative column widths: N°, name, gender, organisation, position, origin, email, phone, signature.
COLUMN_WIDTHS = (7, 32, 10, 30, 25, 25, 32, 26, 38)
# The narrow PDF column; empty (signed before the field existed) is shown like "prefer not to say".
GENDER_SHORT = {"F": "F", "H": "H"}
BLANK_ROW_HEIGHT = 12
BLANK_ROWS_PER_PAGE = 12


def qr(url):
    return segno.make(url, error="m")


def qr_png(url):
    out = BytesIO()
    qr(url).save(out, kind="png", scale=16, border=2)
    return out.getvalue()


def _headers():
    return [
        _("No."), _("Full name"), _("Gender"), _("Organisation represented"), _("Position / title"), _("Origin (city, country)"),
        _("Email"), _("Phone"), _("Signature"),
    ]


class _Pdf(FPDF):
    def __init__(self, title):
        super().__init__(orientation="L", format="A4")
        self.set_margins(10, 10, 10)
        self.set_auto_page_break(True, margin=12)
        self.set_title(title)
        self.unicode = os.path.exists(f"{FONT_DIR}/DejaVuSans.ttf")
        if self.unicode:
            self.add_font("DejaVu", "", f"{FONT_DIR}/DejaVuSans.ttf")
            self.add_font("DejaVu", "B", f"{FONT_DIR}/DejaVuSans-Bold.ttf")
        self.family = "DejaVu" if self.unicode else "Helvetica"

    def text_of(self, value):
        # Without the DejaVu font, only Latin-1 can be written.
        value = str(value or "")
        return value if self.unicode else value.encode("latin-1", "replace").decode("latin-1")

    def footer(self):
        self.set_y(-10)
        self.set_font(self.family, size=7)
        self.cell(0, 5, self.text_of(f"{self.title} · {self.page_no()}/{{nb}}"), align="R")

    def heading(self, event, day, summary=""):
        self.set_font(self.family, "B", 13)
        self.multi_cell(0, 7, self.text_of(event.title), new_x="LMARGIN", new_y="NEXT")
        self.set_font(self.family, size=10)
        line = _("Attendance list") + " · " + formats.date_format(day, "DATE_FORMAT") if day else _("Attendance list")
        if summary:
            line += " · " + summary
        self.cell(0, 6, self.text_of(line), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def table_of(self, rows, line_height=5):
        self.set_font(self.family, size=8)
        style = FontFace(emphasis="BOLD", fill_color=HEADER_FILL)
        with self.table(col_widths=COLUMN_WIDTHS, line_height=line_height, headings_style=style,
                        text_align="LEFT", repeat_headings=1) as table:
            header = table.row()
            for text in _headers():
                header.cell(self.text_of(text))
            for values in rows:
                row = table.row()
                for value in values:
                    if isinstance(value, bytes):
                        row.cell(img=BytesIO(value), img_fill_width=True)
                    else:
                        row.cell(self.text_of(value))


def attendance_pdf(event, day=None):
    """The signed list, one section per day (or only ``day``), with the signatures."""
    pdf = _Pdf(event.title)
    days = [day] if day else event.days()
    for current in days:
        attendances = list(event.attendances.filter(day=current))
        if day is None and not attendances:
            continue
        pdf.add_page()
        summary = gender_summary(gender_counts(a.gender for a in attendances)) if attendances else ""
        pdf.heading(event, current, summary)
        pdf.table_of([
            (a.number, a.full_name, GENDER_SHORT.get(a.gender, "–"), a.organisation, a.position, f"{a.city}, {a.country}", a.email, a.phone,
             bytes(a.signature))
            for a in attendances
        ])
        pdf.set_font(pdf.family, size=7)
        pdf.cell(0, 5, pdf.text_of(_("Gender: F = female, H = male, – = prefer not to say")),
                 new_x="LMARGIN", new_y="NEXT")
    if not pdf.page_no():
        pdf.add_page()
        pdf.heading(event, day)
        pdf.set_font(pdf.family, size=10)
        pdf.cell(0, 8, pdf.text_of(_("Nobody has signed yet.")))
    return bytes(pdf.output())


def blank_pdf(event, pages=3):
    """Empty numbered rows to print, for those who sign on paper."""
    pdf = _Pdf(event.title)
    for page in range(pages):
        pdf.add_page()
        pdf.heading(event, None)
        pdf.set_font(pdf.family, size=10)
        pdf.cell(0, 6, pdf.text_of(_("Date:") + " ____ / ____ / ________"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        pdf.table_of([])
        widths = [pdf.epw * w / sum(COLUMN_WIDTHS) for w in COLUMN_WIDTHS]
        pdf.set_font(pdf.family, size=8)
        for n in range(BLANK_ROWS_PER_PAGE):
            for col, width in enumerate(widths):
                pdf.cell(width, BLANK_ROW_HEIGHT, str(page * BLANK_ROWS_PER_PAGE + n + 1) if col == 0 else "",
                         border=1)
            pdf.ln(BLANK_ROW_HEIGHT)
    return bytes(pdf.output())


def attendance_xlsx(event):
    """Every signature as a row, without the signature image (the PDF carries it)."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = _("Attendance list")[:31]
    headers = [
        _("Day"), _("No."), _("Full name"), _("Gender"), _("Organisation represented"), _("Position / title"),
        _("Country of origin"), _("City of origin"), _("Email"), _("Phone"), _("Signed at"),
    ]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DDEBF7")
    from fieldmonitoring.core.models import ProgrammeConfig

    tz = ProgrammeConfig.get().tz
    for a in event.attendances.defer("signature"):
        sheet.append([
            a.day, a.number, a.full_name, a.get_gender_display(), a.organisation, a.position, a.country, a.city, a.email, a.phone,
            timezone.localtime(a.created_at, tz).strftime("%H:%M"),
        ])
    for row in sheet.iter_rows(min_row=2, max_col=1):
        row[0].number_format = "DD/MM/YYYY"
    columns = {col: [header] for col, header in enumerate(headers, start=1)}
    for row in sheet.iter_rows(min_row=2, values_only=True):
        for col, value in enumerate(row, start=1):
            columns[col].append(value)
    columns[1] = [headers[0], "00/00/0000"]
    fit_columns(sheet, columns)
    sheet.freeze_panes = "A2"
    out = BytesIO()
    workbook.save(out)
    return out.getvalue()
