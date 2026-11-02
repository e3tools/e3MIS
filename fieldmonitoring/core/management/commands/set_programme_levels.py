"""Say which administrative levels play the region, commune and village roles.

    manage.py set_programme_levels --region Département --commune Commune --village Village

Without this, the levels are guessed from the tree position (fieldmonitoring/core/geography.py),
which is wrong for a tree with a level between commune and village (Benin's arrondissements).
With no option, prints the current setting and the available levels.
"""
from django.core.management.base import BaseCommand, CommandError

from administrativelevels.models import AdministrativeLevel
from fieldmonitoring.core.models import ProgrammeConfig

ROLES = ("region", "commune", "village")


class Command(BaseCommand):
    help = "Set the administrative levels that play the region, commune and village roles."

    def add_arguments(self, parser):
        for role in ROLES:
            parser.add_argument(f"--{role}", help=f"Name of the level playing the {role} role")

    def handle(self, *args, **options):
        config = ProgrammeConfig.get()
        changed = []
        for role in ROLES:
            name = options[role]
            if not name:
                continue
            level = AdministrativeLevel.objects.filter(name__iexact=name).first()
            if level is None:
                names = ", ".join(AdministrativeLevel.objects.values_list("name", flat=True))
                raise CommandError(f"No level named {name!r}. Levels: {names}")
            setattr(config, f"{role}_level", level)
            changed.append(f"{role}_level")
        if changed:
            config.save(update_fields=changed + ["updated_at"])
        for role in ROLES:
            level = getattr(config, f"{role}_level")
            self.stdout.write(f"{role}: {level.name if level else '(not set: guessed from the tree)'}")
        if not changed:
            levels = ", ".join(f"{lv.order}. {lv.name}" for lv in AdministrativeLevel.objects.order_by("order"))
            self.stdout.write(f"Levels: {levels}")
