"""
Persistence helpers for the schema-driven dynamic forms.

These centralise the cleaned-data → ``jsonForm`` conversion that was previously
copy-pasted across the mobile create/update views, so the staff-facing edit
views and the mobile views can share one implementation.
"""
import datetime


def serialize_for_json(data):
    """Recursively convert ``datetime`` values to ISO strings (JSON-safe)."""
    if isinstance(data, dict):
        return {k: serialize_for_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [serialize_for_json(item) for item in data]
    if isinstance(data, (datetime.date, datetime.datetime)):
        return data.isoformat()
    return data


def build_json_form(form):
    """Turn a validated dynamic form's ``cleaned_data`` into a JSON-safe dict.

    Mirrors the write path used by the mobile create/update views:
      - ``datetime`` values become ISO strings,
      - uploaded files become the ``'Attachment'`` marker (the real file is
        stored as a separate ``Attachment`` row by the caller),
      - model instances become their primary key.
    """
    cleaned = serialize_for_json(form.cleaned_data)
    files = form.files or {}
    for key in list(cleaned.keys()):
        if key in files:
            cleaned[key] = 'Attachment'
        value = cleaned[key]
        if hasattr(value, 'id') and hasattr(value, '_meta'):
            cleaned[key] = value.id
    return cleaned
