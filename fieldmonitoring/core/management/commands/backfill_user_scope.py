"""Bring existing users in line with "role + one administrative unit" (Brice, 29 Oct 2026).

    manage.py backfill_user_scope            # report only
    manage.py backfill_user_scope --apply    # make the changes

- FT, FC, SC with a commune but no unit: the commune becomes their unit (form 1 offers the
  villages of the agent's units, so an agent without a unit would get none).
- Same roles with one unit but no commune: the commune is worked out from the unit. Regional
  specialists likewise with their region.
- FT, FC without a supervisor: the SC of their commune when it has exactly one.
Users it cannot settle (several units, no unit and no commune, a unit outside any commune) are
listed for an admin to fix on the field-agents page.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from authorization import hierarchy
from authorization.models import FACILITATOR_ROLES, CustomUser, Role

SCOPE = {Role.FT: "commune", Role.FC: "commune", Role.SC: "commune", Role.REGIONAL_SPECIALIST: "region"}


class Command(BaseCommand):
    help = "Fill units, communes, regions and supervisors from each other (report unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Save the changes (default: report only)")

    def handle(self, *args, **options):
        apply = options["apply"]
        changes, problems = [], []
        with transaction.atomic():
            users = CustomUser.objects.filter(is_active=True, role__in=SCOPE).prefetch_related("administrative_units")
            for user in users.order_by("role", "email"):
                field = SCOPE[user.role]
                current = getattr(user, field)
                units = list(user.administrative_units.all())
                if not units and current is None:
                    problems.append(f"{user.email} ({user.role}): no unit and no {field}")
                elif not units:
                    changes.append(f"{user.email}: unit := {current.name}")
                    if apply:
                        user.administrative_units.add(current)
                elif len(units) > 1:
                    problems.append(f"{user.email} ({user.role}): {len(units)} units, choose one")
                elif current is None:
                    commune, region = hierarchy.scope_for(user.role, units[0])
                    found = commune if field == "commune" else region
                    if found is None:
                        problems.append(f"{user.email} ({user.role}): unit {units[0].name} is not in a {field}")
                    else:
                        changes.append(f"{user.email}: {field} := {found.name}")
                        if apply:
                            CustomUser.objects.filter(pk=user.pk).update(**{field: found})

            # Supervisors once every commune is known.
            for user in CustomUser.objects.filter(
                is_active=True, role__in=FACILITATOR_ROLES, supervisor__isnull=True, commune__isnull=False
            ).order_by("email"):
                supervisor, candidates = hierarchy.supervisor_for(user, user.commune_id)
                if supervisor is not None:
                    changes.append(f"{user.email}: supervisor := {supervisor}")
                    if apply:
                        CustomUser.objects.filter(pk=user.pk).update(supervisor=supervisor)
                elif len(candidates) > 1:
                    problems.append(f"{user.email}: several SCs in the commune, choose the supervisor")
                else:
                    problems.append(f"{user.email}: no SC in the commune yet (reviews go to the RdP)")

        for line in changes:
            self.stdout.write(line)
        for line in problems:
            self.stdout.write(self.style.WARNING(line))
        verb = "Applied" if apply else "Would apply (run with --apply)"
        self.stdout.write(f"{verb}: {len(changes)} change(s); {len(problems)} to fix by hand.")
