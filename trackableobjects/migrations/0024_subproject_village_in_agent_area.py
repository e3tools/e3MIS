"""Form 1 ("Sous-projet") offers only the villages of the agent's own units (Brice, 29 Oct 2026).

Production's form may have been edited in the MIS, so only the village field's validators change;
re-running seed_suivi_chantier would overwrite the rest. Reversing removes the restriction.
"""
from django.db import migrations

RECORD = "Sous-projet"


def _set(apps, value):
    TrackableObject = apps.get_model("trackableobjects", "TrackableObject")
    for record in TrackableObject.objects.filter(name=RECORD):
        changed = False
        for page in (record.jsonForm or {}).get("form", []):
            field = page.get("page", {}).get("properties", {}).get("village")
            if not field or field.get("type") != "administrative_level":
                continue
            validators = field.setdefault("validators", {})
            if value:
                changed |= validators.get("administrative_level_restriction") != "true"
                validators["administrative_level_restriction"] = "true"
            elif "administrative_level_restriction" in validators:
                del validators["administrative_level_restriction"]
                changed = True
        if changed:
            # Historical models skip VersionedSchemaMixin.save(): bump the version here.
            record.schema_version += 1
            record.save(update_fields=["jsonForm", "schema_version", "updated_at"])


def restrict(apps, schema_editor):
    _set(apps, True)


def unrestrict(apps, schema_editor):
    _set(apps, False)


class Migration(migrations.Migration):

    dependencies = [
        ("trackableobjects", "0023_visit_forms"),
    ]

    operations = [
        migrations.RunPython(restrict, unrestrict),
    ]
