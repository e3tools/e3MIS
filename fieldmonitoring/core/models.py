import uuid
from datetime import time
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import models


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


def default_working_days():
    return [0, 1, 2, 3, 4]  # Mon–Fri, Python weekday numbers


class ProgrammeConfig(models.Model):
    """Operational parameters (Story 6.6). A single row, editable without a release."""

    timezone = models.CharField(max_length=64, default=settings.PROGRAMME_TIMEZONE_DEFAULT)
    working_days = models.JSONField(default=default_working_days)
    default_tolerance_m = models.PositiveIntegerField(default=100)
    # Check-in radius by village zone (AdministrativeUnit.zone); default_tolerance_m when unknown.
    urban_tolerance_m = models.PositiveIntegerField(default=50)
    rural_tolerance_m = models.PositiveIntegerField(default=100)
    max_accuracy_m = models.PositiveIntegerField(default=100)
    auto_close_time = models.TimeField(default=time(20, 0))
    # Visits checked in less than this long before the auto-close time are left
    # for the next night's run, so someone who arrives at 19:55 can still check out.
    auto_close_grace_minutes = models.PositiveIntegerField(default=60)
    review_sla_hours = models.PositiveIntegerField(default=72)
    rotation_window_days = models.PositiveIntegerField(default=30)
    max_pause_days = models.PositiveIntegerField(default=30)
    impossible_travel_kmh = models.PositiveIntegerField(default=120)
    nearby_radius_m = models.PositiveIntegerField(default=500)
    warning_weekday = models.PositiveSmallIntegerField(default=0)  # Monday
    warning_time = models.TimeField(default=time(6, 0))
    photo_reuse_window_days = models.PositiveIntegerField(default=90)
    photo_hash_max_distance = models.PositiveSmallIntegerField(default=6)
    national_at_risk_working_days = models.PositiveSmallIntegerField(default=10)
    capture_token_ttl_minutes = models.PositiveIntegerField(default=15)
    # Verified visits shorter than this are flagged to the supervisor as possible drive-bys. A
    # warning only: the visit stays verified (non-negotiable 5).
    short_visit_minutes = models.PositiveIntegerField(default=5)
    # How long a phone may stay offline and still prove when a visit happened (trusted clock, Q7).
    max_offline_hours = models.PositiveIntegerField(default=72)
    # Which administrative levels play the field monitoring roles. Left empty, the tree position
    # is used: a worksite's unit is the village, its parent the commune, the next one the region.
    region_level = models.ForeignKey(
        "administrativelevels.AdministrativeLevel", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    commune_level = models.ForeignKey(
        "administrativelevels.AdministrativeLevel", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    village_level = models.ForeignKey(
        "administrativelevels.AdministrativeLevel", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "programme configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls) -> "ProgrammeConfig":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def tolerance_for(self, village) -> int:
        """Check-in radius for a new worksite in ``village``: 50 m urban, 100 m rural by default."""
        zone = getattr(village, "zone", "")
        if zone == "urban":
            return self.urban_tolerance_m
        if zone == "rural":
            return self.rural_tolerance_m
        return self.default_tolerance_m


class ConfigChange(UUIDModel):
    """Append-only audit of configuration and threshold changes."""

    key = models.CharField(max_length=64)
    old_value = models.TextField(blank=True)
    new_value = models.TextField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]


class JobRun(models.Model):
    """Records that a scheduled job ran for a given programme-time key, for idempotency."""

    job = models.CharField(max_length=64)
    run_key = models.CharField(max_length=32)
    ran_at = models.DateTimeField(auto_now_add=True)
    detail = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["job", "run_key"], name="unique_job_run")]
