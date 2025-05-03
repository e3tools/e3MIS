import pandas as pd
from django.core.management.base import BaseCommand
from subprojects.models import Subproject
from administrativelevels.models import AdministrativeLevel  # if used
from decimal import Decimal

KNOWN_FIELDS = {
    "name": "name",
    "description": "description",
    "external_id": "external_id",
    # You can add more direct mappings here if needed
}

class Command(BaseCommand):
    help = 'Import subprojects from an Excel file'

    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='Path to the Excel file')

    def handle(self, *args, **options):
        file_path = options['excel_file']
        df = pd.read_excel(file_path)

        for _, row in df.iterrows():
            known_data = {}
            custom_data = {}

            for excel_col, value in row.items():
                field = KNOWN_FIELDS.get(excel_col)
                if field:
                    known_data[field] = value
                else:
                    if pd.notna(value):
                        custom_data[excel_col.strip()] = value

            if not known_data.get("name"):
                self.stdout.write(self.style.WARNING("Skipping row without 'Intitulé du sous projet'"))
                continue

            subproject = Subproject(
                name=known_data.get("name"),
                description=known_data.get("description", ""),
                external_id=known_data.get("external_id", ""),
                custom_fields=custom_data
            )

            try:
                subproject.save()
                self.stdout.write(self.style.SUCCESS(f"Imported: {subproject.name}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error saving row: {e}"))
