import csv
import os
from django.core.management.base import BaseCommand
from django.conf import settings

from administrativelevels.models import AdministrativeLevel, AdministrativeUnit


class Command(BaseCommand):
    help = 'Initialize administrative levels.'
    filename = 'administrativelevels/management/benin_admin_divisions.csv'

    def __init__(self):
        super(Command, self).__init__()
        self.department = AdministrativeLevel.objects.get(name='Department', order=1)
        self.commune = AdministrativeLevel.objects.get(name='Commune', order=2)
        self.arrondissement = AdministrativeLevel.objects.get(name='Arrondissement', order=3)

    def handle(self, *args, **options):
        file_path = os.path.join(settings.BASE_DIR, self.filename)

        try:
            with open(file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    try:
                        parent = self.get_parent(row)
                        AdministrativeUnit.objects.get_or_create(name=row['Arrondissement'], level=self.arrondissement,
                                                                 parent=parent)
                    except Exception as e:
                        pass
        except FileNotFoundError:
            print(f"File {self.filename} not found in project root.")

    def get_parent(self, child=None):
        try:
            return AdministrativeUnit.objects.get(name=child['Commune'], level=self.commune)
        except AdministrativeUnit.DoesNotExist:
            department = AdministrativeUnit.objects.get_or_create(name=child['Department'], level=self.department)[0]
            return AdministrativeUnit.objects.get_or_create(name=child['Commune'], level=self.commune, parent=department)[0]
