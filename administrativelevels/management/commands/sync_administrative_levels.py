import pandas as pd
from django.core.management.base import BaseCommand
from administrativelevels.models import AdministrativeLevel, AdministrativeUnit
from django.db import transaction

class Command(BaseCommand):
    help = "Dynamically loads administrative units from Excel based on levels defined in the database"

    def add_arguments(self, parser):
        parser.add_argument('excel_path', type=str, help="Path to the Excel file")

    def handle(self, *args, **kwargs):
        path = kwargs['excel_path']
        df = pd.read_excel(path)

        # Normalize column names
        df.columns = [str(col).strip() for col in df.columns]

        # Get levels ordered by hierarchy
        levels = list(AdministrativeLevel.objects.all().order_by('order'))
        level_count = len(levels)

        if df.shape[1] < level_count:
            self.stderr.write(self.style.ERROR(f"Expected at least {level_count} columns in the Excel file. Found {df.shape[1]}"))
            return

        created_units = 0
        level_name_to_instance = {}  # cache of created units to avoid duplicates

        with transaction.atomic():
            for _, row in df.iterrows():
                parent = None
                for idx, level in enumerate(levels):
                    name = str(row[idx]).strip()
                    key = (name, level.id, parent.id if parent else None)

                    # Cache check to avoid redundant DB hits
                    if key in level_name_to_instance:
                        unit = level_name_to_instance[key]
                    else:
                        unit, _ = AdministrativeUnit.objects.get_or_create(
                            name=name,
                            level=level,
                            parent=parent
                        )
                        level_name_to_instance[key] = unit
                        if level == levels[-1]:  # only count lowest level created
                            created_units += 1

                    parent = unit  # Set for next level down

        self.stdout.write(self.style.SUCCESS(
            f"Administrative units created or matched successfully. {created_units} lowest-level units added."))