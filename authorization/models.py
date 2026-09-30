from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    """Field monitoring roles. Roles drive visit rules and supervision; groups decide which forms
    a user sees. Existing MIS users may have no role."""
    FT = "ft", "Facilitateur technique"
    FC = "fc", "Facilitateur communautaire"
    SC = "sc", "Superviseur communal"
    REGIONAL_SPECIALIST = "regional_specialist", "Spécialiste régional"
    NATIONAL_SPECIALIST = "national_specialist", "Spécialiste national"
    RDP = "rdp", "Responsable du projet"
    ADMIN = "admin", "Administrateur"


FIELD_STAFF_ROLES = {Role.FT, Role.FC, Role.SC}
FACILITATOR_ROLES = {Role.FT, Role.FC}
SPECIALIST_ROLES = {Role.REGIONAL_SPECIALIST, Role.NATIONAL_SPECIALIST}
VISITING_ROLES = FIELD_STAFF_ROLES | SPECIALIST_ROLES


class DeviceClass(models.TextChoices):
    ISSUED = "issued", "Issued"
    PERSONAL = "personal", "Personal"


def _today():
    return timezone.localdate()


class CustomUserManager(BaseUserManager):
    def get_by_natural_key(self, username):
        return self.get(**{self.model.USERNAME_FIELD: username})

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class AppSettings(models.Model):
    show_all_activities_button = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Settings'
        verbose_name_plural = 'Settings'

    def __str__(self):
        return 'App Settings'

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class CustomUser(AbstractUser):
    username = None
    email = models.EmailField('email address', unique=True)
    is_field_agent = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    administrative_units = models.ManyToManyField(
        'administrativelevels.AdministrativeUnit',
        blank=True
    )

    # --- Field monitoring -------------------------------------------------------------------
    full_name = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=32, choices=Role.choices, blank=True)
    # The SC for an FT/FC. Defines team views, review routing and warning filtering.
    supervisor = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="team"
    )
    # The supervision area (unit at the programme's "commune" level) and, for regional
    # specialists, the unit at the "region" level. See ProgrammeConfig.commune_level.
    commune = models.ForeignKey(
        "administrativelevels.AdministrativeUnit", null=True, blank=True,
        on_delete=models.PROTECT, related_name="commune_staff",
    )
    region = models.ForeignKey(
        "administrativelevels.AdministrativeUnit", null=True, blank=True,
        on_delete=models.PROTECT, related_name="region_staff",
    )
    # Weights the mock-location signal (DEC-7, BR-12).
    device_class = models.CharField(
        max_length=16, choices=DeviceClass.choices, default=DeviceClass.PERSONAL
    )
    # BR-2 baseline when a user has no verified visit yet.
    onboarded_on = models.DateField(default=_today)
    preferred_language = models.CharField(max_length=8, default="fr")

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        ordering = ["full_name", "email"]

    def __str__(self):
        return self.full_name or self.email

    @property
    def username(self) -> str:
        """Read-only alias: the field monitoring API and apps call the sign-in name 'username'."""
        return self.email

    @property
    def is_field_staff(self) -> bool:
        return self.role in FIELD_STAFF_ROLES

    @property
    def is_specialist(self) -> bool:
        return self.role in SPECIALIST_ROLES

    @property
    def records_visits(self) -> bool:
        return self.role in VISITING_ROLES

    def clean(self):
        """Story 1.1: hierarchy rules."""
        super().clean()
        if self.role in FACILITATOR_ROLES:
            if not self.supervisor_id:
                raise ValidationError({"supervisor": "An FT or FC must have an SC as supervisor."})
            if self.supervisor.role != Role.SC:
                raise ValidationError({"supervisor": "The supervisor of an FT or FC must be an SC."})
            if not self.commune_id or self.supervisor.commune_id != self.commune_id:
                raise ValidationError(
                    {"supervisor": "The supervisor must be an SC in the same commune."}
                )
        elif self.supervisor_id:
            # SCs and above have no supervisor; their visits route to the RdP (BR-10).
            raise ValidationError({"supervisor": "Only FTs and FCs have a supervisor."})
        if self.role in FIELD_STAFF_ROLES and not self.commune_id:
            raise ValidationError({"commune": "FT, FC and SC users need a commune."})
        if self.role == Role.REGIONAL_SPECIALIST and not self.region_id:
            raise ValidationError({"region": "A regional specialist needs a region."})
        # With FT/FC -> SC and SC -> nobody, a chain has depth one and cannot cycle.
        # Checked explicitly anyway so a future role change cannot introduce one.
        seen, node = {self.pk}, self.supervisor
        while node is not None:
            if node.pk in seen:
                raise ValidationError({"supervisor": "The supervisor chain contains a cycle."})
            seen.add(node.pk)
            node = node.supervisor

    def save(self, *args, **kwargs):
        if not self.full_name:
            self.full_name = self.get_full_name() or self.email
        # Anyone who records visits uses the field screens; the role is the source of truth.
        if self.role:
            self.is_field_agent = self.role in VISITING_ROLES
        super().save(*args, **kwargs)


# The field monitoring code refers to the user model as ``User``.
User = CustomUser
