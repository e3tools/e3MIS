#django command that recieves a string as administrative level and creates a user with that administrative level

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from administrativelevels.models import AdministrativeLevel, AdministrativeUnit
from django.core.exceptions import ObjectDoesNotExist
from django.utils.text import slugify
from django.db import transaction
from django.contrib.auth.hashers import make_password
from django.core.management import CommandError
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import random
import string


def generate_password(length=12):
    if length < 6:
        raise ValueError("Password length should be at least 6 characters")

    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.SystemRandom().choice(characters) for _ in range(length))
    return password

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a user with a specified administrative level'

    def add_arguments(self, parser):
        parser.add_argument('administrative_level_name', type=str, help='Name of the administrative level')
        parser.add_argument('domain', type=str, help='Name domain')

    @transaction.atomic
    def handle(self, *args, **options):
        administrative_level_name = options['administrative_level_name']

        try:
            administrative_level = AdministrativeLevel.objects.get(name=administrative_level_name)
        except ObjectDoesNotExist:
            raise CommandError(f"Administrative level '{administrative_level_name}' does not exist.")

        administrative_units = AdministrativeUnit.objects.filter(level=administrative_level)

        for administrative_unit in administrative_units:
            base_slug = slugify(administrative_unit.name)
            base_email = f"{base_slug}@{options['domain']}"
            email = base_email
            suffix = 1

            # Check for duplicate with same or different administrative_unit
            while True:
                existing_user = User.objects.filter(email=email).first()
                if not existing_user:
                    break
                elif existing_user.administrative_unit == administrative_unit:
                    self.stdout.write(self.style.WARNING(
                        f"User with email '{email}' and same administrative unit already exists. Skipping."
                    ))
                    email = None
                    break
                else:
                    email = f"{base_slug}{suffix}@{options['domain']}"
                    suffix += 1

            if not email:
                continue

            try:
                validate_email(email)
            except ValidationError:
                raise CommandError(f"Invalid email format for '{email}'.")

            password = generate_password(length=8)

            user = User(
                email=email,
                password=make_password(password),
                administrative_unit=administrative_unit,
                is_field_agent=True,
            )
            user.save()
            print(f"Created user: {user.email} for administrative level: {administrative_level.name} with password: {password}")

        self.stdout.write(self.style.SUCCESS(f"Users created with administrative level '{administrative_level.name}'"))