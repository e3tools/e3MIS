from django.core.management.base import BaseCommand
from subprojects.models import Subproject
from administrativelevels.models import AdministrativeUnit

class Command(BaseCommand):
    help = 'Update administrative_level for subprojects from custom_fields["Communauté"]'

    def handle(self, *args, **options):
        updated_count = 0
        skipped_count = 0

        subprojects = Subproject.objects.all()

        for subproject in subprojects:
            custom = subproject.custom_fields or {}
            communaute = custom.get("Communauté")

            if communaute:
                try:
                    admin_unit = AdministrativeUnit.objects.get(
                        name=communaute.strip(),
                        level__order=4  # village/communauté level
                    )
                except AdministrativeUnit.DoesNotExist:
                    skipped_count += 1
                    self.stdout.write(self.style.WARNING(
                        f"No level 4 AdministrativeUnit found for '{communaute}'"
                    ))
                    continue
                except AdministrativeUnit.MultipleObjectsReturned:
                    skipped_count += 1
                    self.stdout.write(self.style.ERROR(
                        f"Multiple level 4 AdministrativeUnits found for '{communaute}'"
                    ))
                    continue

                subproject.administrative_level = admin_unit
                del custom["Communauté"]
                subproject.custom_fields = custom
                subproject.save()

                updated_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f"Updated '{subproject.name}' with administrative unit '{admin_unit.name}'"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"\nUpdate complete: {updated_count} updated, {skipped_count} skipped"
        ))
