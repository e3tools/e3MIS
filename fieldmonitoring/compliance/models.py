from django.conf import settings
from django.db import models

from fieldmonitoring.core.models import UUIDModel


class RoleThreshold(models.Model):
    """DEC-2 / Story 6.1: one regularity threshold per role, programme-wide.

    Launch values (FT 10, FC 10, SC 14) are placeholders pending baseline data.
    """

    ROLE_CHOICES = [("ft", "FT"), ("fc", "FC"), ("sc", "SC")]
    LAUNCH_VALUES = {"ft": 10, "fc": 10, "sc": 14}

    role = models.CharField(max_length=8, choices=ROLE_CHOICES, primary_key=True)
    days = models.PositiveIntegerField()
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def as_dict(cls) -> dict[str, int]:
        values = dict(cls.LAUNCH_VALUES)
        values.update(dict(cls.objects.values_list("role", "days")))
        return values


class Pause(UUIDModel):
    """BR-4. Append-only history: cancel, never delete. `ends_on` is the resume day."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pauses")
    starts_on = models.DateField()
    ends_on = models.DateField()
    reason = models.TextField()
    set_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    set_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-starts_on"]

    def delete(self, *args, **kwargs):
        raise RuntimeError("Pauses are append-only. Cancel instead of deleting.")
