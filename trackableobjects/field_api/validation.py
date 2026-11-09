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
- ``validators.min_value`` / ``max_value`` of numbers: the MIS form only sets them on the browser
  input, so they are checked here for the app (e.g. an execution rate of at most 100 %).
- ``validators.max_field``: a number must not be above another answer, e.g. the women among the
  workers present not more than the workers present (COSO 2.15, Brice 5 Nov 2026).
"""
from django import forms

from trackableobjects import visibility
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
        unit_ids = visibility.own_unit_ids_with_descendants(user)

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


def _compare(value, other) -> int:
    """-1, 0 or 1. Numbers as numbers; ISO dates compare as text."""
    try:
        a, b = float(value), float(other)
    except (TypeError, ValueError):
        a, b = str(value), str(other)
    return (a > b) - (a < b)


def _cross_field_errors(schema, clean, errors) -> dict:
    found = {}
    options = field_options(schema)
    for page in pages(schema):
        for name, prop in page.get("page", {}).get("properties", {}).items():
            validators = prop.get("validators") or {}
            # The MIS form only puts min/max on the browser input; check them here for the app.
            if prop.get("type") in ("number", "integer") and name not in errors and clean.get(name) not in (None, ""):
                for key, wrong, message in (
                    ("min_value", -1, "Must be at least {limit}."),
                    ("max_value", 1, "Must be at most {limit}."),
                ):
                    limit = validators.get(key)
                    if limit not in (None, "") and name not in found and _compare(clean[name], limit) == wrong:
                        found[name] = [message.format(limit=limit)]
            for key, wrong, message in (
                ("min_field", -1, "Must not be before “{label}”."),
                ("max_field", 1, "Must not be more than “{label}”."),
            ):
                other = validators.get(key)
                if not other or name in errors or name in found:
                    continue
                if clean.get(name) in (None, "") or clean.get(other) in (None, ""):
                    continue
                if _compare(clean[name], clean[other]) == wrong:
                    label = options.get(other, {}).get("label") or other
                    found[name] = [message.format(label=label)]
    return found
