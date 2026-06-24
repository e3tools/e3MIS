"""
Turn dynamic-form submissions into downloadable CSV / XLSX files.

Builds on :func:`utils.submission_table.build_submission_table` (run with
``as_text=True``) so exports mirror the on-screen tables, then prepends/appends
caller-supplied metadata columns (id, created by, group, ...).
"""
import csv
from io import BytesIO

import openpyxl
from django.http import HttpResponse


def build_export_table(schema_fields, rows, leading_columns=None, trailing_columns=None):
    """Return ``(header, data_rows)`` ready for CSV/XLSX writers.

    ``leading_columns`` / ``trailing_columns`` are lists of
    ``(header_label, lambda submission: value)`` placed before / after the
    schema-field columns.
    """
    leading_columns = leading_columns or []
    trailing_columns = trailing_columns or []

    header = (
        [label for label, _ in leading_columns]
        + [field['label'] for field in schema_fields]
        + [label for label, _ in trailing_columns]
    )

    data = []
    for row in rows:
        submission = row['instance']
        line = [getter(submission) for _, getter in leading_columns]
        line += [str(cell) for cell in row['cells']]
        line += [getter(submission) for _, getter in trailing_columns]
        data.append(line)

    return header, data


def csv_response(filename, header, data):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="{}.csv"'.format(filename)
    writer = csv.writer(response)
    writer.writerow(header)
    for line in data:
        writer.writerow(line)
    return response


def xlsx_response(filename, header, data, sheet_title='Submissions'):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = sheet_title[:31]  # Excel caps sheet titles at 31 chars.
    sheet.append(header)
    for line in data:
        sheet.append(line)

    buffer = BytesIO()
    workbook.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="{}.xlsx"'.format(filename)
    return response


def export_response(fmt, filename, header, data, sheet_title='Submissions'):
    """Dispatch to the CSV or XLSX writer based on ``fmt``."""
    if fmt == 'xlsx':
        return xlsx_response(filename, header, data, sheet_title)
    return csv_response(filename, header, data)
