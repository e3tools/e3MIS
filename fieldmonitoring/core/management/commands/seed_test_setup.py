"""A small Benin-shaped setup for trying the MIS by hand. Development and local tests only.

    manage.py seed_test_setup [--sc-password <password>]

Creates the four levels (Department → Commune → Arrondissement → Village), a few sample units (with two
villages named "Gah" in different arrondissements, to try homonyms), the facilitator and
supervisor groups with their default role, and maps the levels in ProgrammeConfig. The sample
units are only added to an empty tree: after sync_administrative_levels, the real ones are kept. With
``--sc-password``, also creates one communal supervisor for Nikki (sc.nikki@example.org).
Safe to run again: what exists is kept. Refuses a database whose levels are different.
"""
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from administrativelevels.models import AdministrativeLevel, AdministrativeUnit
from authorization.models import GroupRole, Role, User

LEVELS = ["Department", "Commune", "Arrondissement", "Village"]

TREE = {
    "Borgou": {
        "Nikki": {"Nikki": ["Gah", "Sansi", "Tontarou"], "Ouénou": ["Ouénou", "Gah"]},
        "N'Dali": {"N'Dali": ["N'Dali", "Gbégourou"], "Bori": ["Bori", "Sirarou"]},
    },
    "Donga": {
        "Djougou": {"Bariénou": ["Bariénou", "Kakindoni"], "Partago": ["Partago", "Founga"]},
    },
    "Alibori": {
        "Kandi": {"Kandi I": ["Kandi Fô", "Gansosso"]},
    },
}

GROUPS = {
    "Technical facilitator": Role.FT,
    "Community facilitator": Role.FC,
    "Communal supervisor": Role.SC,
}


class Command(BaseCommand):
    help = "Create Benin-shaped levels, a few units and the agent groups, for local tests."

    def add_arguments(self, parser):
        parser.add_argument("--sc-password", help="Also create sc.nikki@example.org with this password")

    @transaction.atomic
    def handle(self, *args, sc_password=None, **options):
        existing = list(AdministrativeLevel.objects.order_by("order").values_list("name", flat=True))
        if existing and existing != LEVELS:
            raise CommandError(f"The database already has other levels: {', '.join(existing)}.")
        levels = [
            AdministrativeLevel.objects.get_or_create(name=name, defaults={"order": order})[0]
            for order, name in enumerate(LEVELS, start=1)
        ]

        if AdministrativeUnit.objects.exists():
            self.stdout.write("Units: the tree already has units, no sample added.")
        else:
            self._sample_units(levels)

        for name, role in GROUPS.items():
            group = Group.objects.get_or_create(name=name)[0]
            GroupRole.objects.update_or_create(group=group, defaults={"role": role})
        self.stdout.write(f"Groups: {', '.join(GROUPS)}.")

        call_command(
            "set_programme_levels", region="Department", commune="Commune", village="Village", stdout=self.stdout,
        )

        if sc_password:
            nikki = AdministrativeUnit.objects.filter(name__iexact="Nikki", level=levels[1]).first()
            if nikki is None:
                raise CommandError("No commune named Nikki for the SC.")
            sc, new = User.objects.get_or_create(
                email="sc.nikki@example.org",
                defaults={"first_name": "Superviseur", "last_name": "Nikki", "role": Role.SC},
            )
            if new:
                sc.set_password(sc_password)
                sc.save()
                sc.administrative_units.add(nikki)
                sc.groups.add(Group.objects.get(name="Communal supervisor"))
                call_command("backfill_user_scope", apply=True, stdout=self.stdout)
            self.stdout.write(f"SC: {sc.email} ({'created' if new else 'already there'}).")

    def _sample_units(self, levels):
        def unit(name, depth, parent):
            return AdministrativeUnit.objects.create(name=name, level=levels[depth], parent=parent)

        for department, communes in TREE.items():
            department_unit = unit(department, 0, None)
            for commune, arrondissements in communes.items():
                commune_unit = unit(commune, 1, department_unit)
                for arrondissement, villages in arrondissements.items():
                    arrondissement_unit = unit(arrondissement, 2, commune_unit)
                    for village in villages:
                        unit(village, 3, arrondissement_unit)
        self.stdout.write(f"Units: {AdministrativeUnit.objects.count()} sample units created.")
