"""Server-side check of answers sent by the field app, reusing the MIS form parser.

The app renders forms itself (offline), so the server re-checks every submission with the same
Django form the MIS screens build from the schema (``utils.json_form_parser``). Differences from a
browser POST:

- Every page of the schema is checked (the web screens only render page 0).
- Fields hidden by display conditions are dropped: not required and not stored.
- File fields are not uploaded with the answers. The app sends the marker ``"Attachment"`` and
  uploads the file separately; a required file field only needs the marker.
- The "use my location" button is a widget, not an answer, and is ignored.
- ``validators.min_field`` (field app extension): a date or number must not be before/below
  another answer of the same form, e.g. the planned end of works after their start (COSO 1.17).
"""
from django import forms

from administrativelevels.models import AdministrativeUnit
from utils.dynamic_form_io import build_json_form
from utils.json_form_parser import (
    evaluate_condition,
    evaluate_multiple_conditions,
    parse_custom_jsonschema,
    schema_requires_assigned_units,
)

ATTACHMENT = "Attachment"


def pages(schema) -> list[dict]:
    if isinstance(schema, dict) and isinstance(schema.get("form"), list):
        return schema["form"]
    return []


def field_options(schema) -> dict:
    """Options (label, order, dependencies…) of every field, across pages."""
    merged = {}
    for page in pages(schema):
        merged.update(page.get("options", {}).get("fields", {}))
    return merged


def _is_shown(meta, answers, parent_data) -> bool:
    dependencies = meta.get("dependencies") or {}
    if not dependencies:
        return True
    if "conditions" in dependencies:
        conditions = dependencies["conditions"]
        results = []
        for condition in conditions:
            source = parent_data if condition.get("is_parent_form") else answers
            results.append(
                evaluate_condition(
                    source.get(condition.get("field")),
                    condition.get("operator", "equals"),
                    condition.get("value", ""),
                )
            )
        return bool(evaluate_multiple_conditions(conditions, results))
    # Old format: {field: {operator, value, is_parent_form}}, all must hold.
    for dep_field, config in dependencies.items():
        source = parent_data if config.get("is_parent_form") else answers
        if not evaluate_condition(source.get(dep_field), config.get("operator", "equals"), config.get("value", "")):
            return False
    return True


def _form_value(value, field):
    """Answers arrive as JSON; turn them into what a bound Django field expects."""
    if isinstance(field, forms.TypedChoiceField) and isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return value


def validate_answers(schema, answers, *, user, parent_data=None):
    """Return ``(clean_answers, errors)``. ``errors`` maps field names to messages."""
    if not isinstance(answers, dict):
        return None, {"__all__": ["Answers must be an object."]}
    parent_data = parent_data or {}
    options = field_options(schema)
    unit_ids = []
    if any(schema_requires_assigned_units(schema, i) for i in range(len(pages(schema)))):
        unit_ids = AdministrativeUnit.get_descendant_ids(user.administrative_units.values_list("id", flat=True))

    clean, errors = {}, {}
    for index in range(len(pages(schema))):
        form_class = parse_custom_jsonschema(
            schema, page_index=index, administrative_level_ids=unit_ids, parent_form_data=parent_data
        )
        form = form_class()
        data, file_fields = {}, {}
        for name, field in list(form.fields.items()):
            if name == "get_geoloc":
                del form.fields[name]
                continue
            if not _is_shown(options.get(name, {}), answers, parent_data):
                del form.fields[name]
                continue
            if isinstance(field, forms.FileField):
                file_fields[name] = field
                del form.fields[name]
                continue
            if name in answers:
                data[name] = _form_value(answers[name], field)
        for name, field in file_fields.items():
            if answers.get(name) == ATTACHMENT:
                clean[name] = ATTACHMENT
            elif field.required:
                errors[name] = ["This file is required."]
        bound = form_class(data=data)
        bound.fields = form.fields
        if bound.is_valid():
            clean.update(build_json_form(bound))
        else:
            errors.update({name: [str(m) for m in messages] for name, messages in bound.errors.items()})
    errors.update(_cross_field_errors(schema, clean, errors))
    return (None, errors) if errors else (clean, {})


def _cross_field_errors(schema, clean, errors) -> dict:
    found = {}
    options = field_options(schema)
    for page in pages(schema):
        for name, prop in page.get("page", {}).get("properties", {}).items():
            other = (prop.get("validators") or {}).get("min_field")
            if not other or name in errors or clean.get(name) in (None, "") or clean.get(other) in (None, ""):
                continue
            value, floor = clean[name], clean[other]
            try:
                too_low = float(value) < float(floor)
            except (TypeError, ValueError):
                too_low = str(value) < str(floor)  # ISO dates compare as text
            if too_low:
                label = options.get(other, {}).get("label") or other
                found[name] = [f"Must not be before “{label}”."]
    return found
