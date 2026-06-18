"""
Helpers to render dynamic-form submissions as a tabular view.

A "submission" is any record that stores its form answers in a ``jsonForm``
dict keyed by the schema field names — i.e. ``TrackableObjectInstance`` or
``FollowUpEventResponse``. The schema itself lives on the parent
``TrackableObject``/``FollowUpEvent`` ``jsonForm`` (``form[*].page.properties``
plus ``form[*].options.fields`` for labels/order).

``build_submission_table`` turns a schema + a list of submissions into:
    - an ordered list of column descriptors (one per schema field), and
    - one row per submission with the answers already formatted for display
      (IDs resolved to names, files turned into links, etc.).
"""
from django.utils.html import format_html
from django.utils.translation import gettext as _

from administrativelevels.models import AdministrativeUnit
from trackableobjects.models import TrackableObjectInstance

EMPTY = '—'
# Stored verbatim by the write path for file fields (see register views).
FILE_SENTINEL = 'Attachment'


def extract_schema_fields(json_form):
    """Return ordered column descriptors from a form schema.

    Each descriptor is ``{'name', 'label', 'type', 'order'}``. Every page is
    walked so multi-page forms are covered. Sorted by the per-field ``order``.
    """
    fields = []
    if not isinstance(json_form, dict):
        return fields

    for page_def in json_form.get('form', []):
        page = page_def.get('page', {})
        options = page_def.get('options', {}).get('fields', {})
        for name, schema in page.get('properties', {}).items():
            meta = options.get(name, {})
            fields.append({
                'name': name,
                'label': meta.get('label', name),
                'order': meta.get('order', 999),
                'type': schema.get('type', 'string'),
            })

    fields.sort(key=lambda f: f['order'])
    return fields


def build_submission_table(json_form, submissions, as_text=False):
    """Build ``(schema_fields, rows)`` for a set of form submissions.

    ``rows`` is a list of ``{'instance': submission, 'cells': [...]}`` where
    each cell aligns positionally with ``schema_fields`` and is already
    formatted for display.

    Reference fields (admin levels, linked trackable objects) are resolved with
    a single batched query each; file fields use the prefetched ``attachments``
    relation, so callers should ``prefetch_related('attachments')``.
    """
    submissions = list(submissions)
    schema_fields = extract_schema_fields(json_form)

    admin_field_names = {f['name'] for f in schema_fields if f['type'] == 'administrative_level'}
    object_field_names = {f['name'] for f in schema_fields if f['type'] == 'trackable_object'}

    # Collect every referenced id up front so each lookup is one query.
    admin_ids, object_ids = set(), set()
    for submission in submissions:
        data = _json_form(submission)
        for name in admin_field_names:
            if _is_id(data.get(name)):
                admin_ids.add(int(data[name]))
        for name in object_field_names:
            if _is_id(data.get(name)):
                object_ids.add(int(data[name]))

    admin_lookup = {}
    if admin_ids:
        for unit in AdministrativeUnit.objects.filter(id__in=admin_ids).select_related('level'):
            admin_lookup[unit.id] = str(unit)

    object_lookup = {}
    if object_ids:
        for instance in TrackableObjectInstance.objects.filter(id__in=object_ids):
            object_lookup[instance.id] = str(instance.identifier)

    rows = []
    for submission in submissions:
        data = _json_form(submission)
        cells = [
            format_cell(field, data.get(field['name']), admin_lookup, object_lookup, submission, as_text=as_text)
            for field in schema_fields
        ]
        rows.append({'instance': submission, 'cells': cells})

    return schema_fields, rows


def format_cell(field, value, admin_lookup, object_lookup, submission, as_text=False):
    """Format a single stored answer.

    ``as_text=False`` renders for the HTML table (file fields become links);
    ``as_text=True`` renders plain text for CSV/XLSX export (file fields become
    the file URL, blanks become an empty string instead of the ``—`` dash).
    """
    field_type = field['type']
    empty = '' if as_text else EMPTY

    if field_type == 'file':
        attachment = _find_attachment(submission, field['name'])
        if attachment and attachment.file:
            if as_text:
                return attachment.file.url
            return format_html('<a href="{}" target="_blank">{}</a>', attachment.file.url, _('View'))
        return empty

    if value is None or value == '':
        return empty

    if field_type == 'administrative_level':
        return admin_lookup.get(int(value), str(value)) if _is_id(value) else str(value)

    if field_type == 'trackable_object':
        return object_lookup.get(int(value), str(value)) if _is_id(value) else str(value)

    if field_type in ('bool', 'boolean'):
        if isinstance(value, bool):
            return _('Yes') if value else _('No')
        if str(value).lower() in ('true', '1', 'yes'):
            return _('Yes')
        if str(value).lower() in ('false', '0', 'no'):
            return _('No')
        return str(value)

    if isinstance(value, (list, tuple)):
        return ', '.join(str(v) for v in value) if value else empty

    return str(value)


def _json_form(submission):
    """Return the submission answers as a dict (default is an empty list)."""
    data = getattr(submission, 'jsonForm', None)
    return data if isinstance(data, dict) else {}


def _find_attachment(submission, field_name):
    attachments = getattr(submission, 'attachments', None)
    if attachments is None:
        return None
    for attachment in attachments.all():
        if attachment.field_name == field_name:
            return attachment
    return None


def _is_id(value):
    """True when ``value`` is a usable foreign-key id (not empty / a sentinel)."""
    if value is None or value == '' or value == FILE_SENTINEL:
        return False
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False
