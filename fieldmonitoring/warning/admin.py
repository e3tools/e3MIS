from django.contrib import admin

from fieldmonitoring.registry.admin import ReadOnlyAdmin

from .models import Warning


@admin.register(Warning)
class WarningAdmin(ReadOnlyAdmin):
    list_display = ("week_of", "generated_at", "paused_count", "total_field_staff")
