from django.conf import settings
from django.db import models

from fieldmonitoring.core.models import UUIDModel


class Warning(UUIDModel):
    """BR-14 weekly warning, stored so week-on-week trend is computable.

    Information only (DEC-6): there is deliberately no acknowledgement, action or
    "handled" field here or on the entries.
    """

    week_of = models.DateField(unique=True, help_text="The Monday the warning is issued")
    period_start = models.DateField()
    period_end = models.DateField()
    generated_at = models.DateTimeField()
    paused_count = models.PositiveIntegerField()
    total_field_staff = models.PositiveIntegerField()
    overdue_high_risk_reviews = models.PositiveIntegerField(default=0)
    thresholds = models.JSONField(default=dict)

    class Meta:
        ordering = ["-week_of"]


class EntryKind(models.TextChoices):
    REGULARITY = "regularity", "Regularity"
    QUOTA = "quota", "Quota"
    ROTATION = "rotation", "Rotation"


class WarningEntry(UUIDModel):
    warning = models.ForeignKey(Warning, on_delete=models.CASCADE, related_name="entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=16, choices=EntryKind.choices)
    rank = models.PositiveIntegerField()
    days_since_last_verified = models.IntegerField(null=True, blank=True)
    # Snapshots at generation time, so historical warnings keep the supervisor and
    # threshold in force that week (Story 6.5).
    role = models.CharField(max_length=32)
    threshold_days = models.PositiveIntegerField(null=True, blank=True)
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    area = models.CharField(max_length=120, blank=True)
    delta_days = models.IntegerField(null=True, blank=True)
    detail = models.JSONField(default=dict)

    class Meta:
        ordering = ["rank"]
