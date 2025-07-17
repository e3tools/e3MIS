import pandas as pd
from django.core.management.base import BaseCommand
from subprojects.models import Subproject
from administrativelevels.models import AdministrativeUnit
from decimal import Decimal

KNOWN_FIELDS = {
    "name": "name",
    "description": "description",
    "external_id": "external_id",
    "Communauté": "administrative_level",  # maps Excel column "Communauté" to the field "administrative_level"
    # Add more field mappings if needed
}

class Command(BaseCommand):
    help = 'Import subprojects from an Excel file'

    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='Path to the Excel file')

    def handle(self, *args, **options):
        file_path = options['excel_file']
        df = pd.read_excel(file_path)

        for index, row in df.iterrows():
            known_data = {}
            custom_data = {}
            admin_unit = None

            for excel_col, value in row.items():
                field = KNOWN_FIELDS.get(excel_col)
                if field:
                    # Handle administrative level separately
                    if field == "administrative_level" and pd.notna(value):
                        try:
                            admin_unit = AdministrativeUnit.objects.get(name=str(value).strip(), level__order=4)
                        except AdministrativeUnit.DoesNotExist:
                            self.stdout.write(self.style.WARNING(
                                f"Row {index + 2}: Level 4 Administrative unit '{value}' not found. Skipping row."
                            ))
                            admin_unit = None
                            break  
                    else:
                        known_data[field] = value
                else:
                    # Store all unmapped fields into custom_fields if not empty
                    if pd.notna(value):
                        custom_data[excel_col.strip()] = value

            if not known_data.get("name"):
                self.stdout.write(self.style.WARNING(f"Row {index + 2}: Skipping row without 'name' / 'Intitulé du sous projet'"))
                continue

            subproject = Subproject(
                name=known_data.get("name"),
                description=known_data.get("description", ""),
                external_id=known_data.get("external_id", ""),
                administrative_level=admin_unit,
                custom_fields=custom_data
            )

            try:
                subproject.save()
                self.stdout.write(self.style.SUCCESS(f"Row {index + 2}: Imported '{subproject.name}'"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Row {index + 2}: Error saving subproject: {e}"))

