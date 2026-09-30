from django.contrib import admin

from fieldmonitoring.registry.admin import ReadOnlyAdmin

from .models import Pause, RoleThreshold


@admin.register(Pause)
class PauseAdmin(ReadOnlyAdmin):
    """Pauses have rules admin will not enforce (BR-4); they are set from the dashboard."""

    list_display = ("user", "starts_on", "ends_on", "set_by", "cancelled_at")


@admin.register(RoleThreshold)
class RoleThresholdAdmin(ReadOnlyAdmin):
    list_display = ("role", "days", "updated_by", "updated_at")
