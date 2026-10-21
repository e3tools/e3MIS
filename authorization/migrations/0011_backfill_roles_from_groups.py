"""Give existing MIS field agents a field monitoring role from their facilitator group (merge plan Q4).

Technical facilitator → FT, Community facilitator → FC. Agents in both groups, in neither, or
already holding a role are left for an admin to set. Reversing leaves roles as they are.
"""
from django.db import migrations

GROUP_ROLES = {"Technical facilitator": "ft", "Community facilitator": "fc"}


def backfill(apps, schema_editor):
    User = apps.get_model("authorization", "CustomUser")
    for user in User.objects.filter(is_field_agent=True, role="").prefetch_related("groups"):
        roles = {GROUP_ROLES[g.name] for g in user.groups.all() if g.name in GROUP_ROLES}
        if len(roles) == 1:
            user.role = roles.pop()
            user.save(update_fields=["role"])


class Migration(migrations.Migration):

    dependencies = [
        ("authorization", "0010_field_monitoring_roles"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
