from django.core.management.base import BaseCommand
import random
import string
from datetime import datetime, timedelta

from subprojects.models import Subproject


class Command(BaseCommand):
    help = 'Generate random subprojects'

    def handle(self, *args, **options):
        markers = [self.generate_marker() for _ in range(20)]
        Subproject.objects.bulk_create(markers)
        print("✅ Inserted 20 random subproject entries.")

    def generate_random_string(self, length=8):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

    def generate_random_coordinates(self):
        # Benin bounding box: lat 6.2–12.4, lon 0.8–3.8
        lat = round(random.uniform(6.2, 12.4), 6)
        lon = round(random.uniform(0.8, 3.8), 6)
        return lat, lon

    def generate_random_date_pair(self):
        start = datetime.today() - timedelta(days=random.randint(0, 365))
        end = start + timedelta(days=random.randint(1, 30))
        return start.date(), end.date()

    def generate_marker(self):
        external_id = self.generate_random_string()
        name = f"Project {self.generate_random_string(4)}"
        description = f"This is a description for marker {external_id}."
        status = random.randint(1, 6)
        start_date, end_date = self.generate_random_date_pair()
        latitude, longitude = self.generate_random_coordinates()

        return Subproject(
            external_id=external_id,
            name=name,
            description=description,
            status=status,
            start_date=start_date,
            end_date=end_date,
            latitude=latitude,
            longitude=longitude
        )
