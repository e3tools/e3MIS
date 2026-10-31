from django.contrib import admin

from fieldmonitoring.registry.admin import ReadOnlyAdmin

from .models import ConfigChange, JobRun, ProgrammeConfig


@admin.register(ConfigChange)
class ConfigChangeAdmin(ReadOnlyAdmin):
    list_display = ("key", "old_value", "new_value", "changed_by", "changed_at")


@admin.register(JobRun)
class JobRunAdmin(ReadOnlyAdmin):
    list_display = ("job", "run_key", "ran_at")


@admin.register(ProgrammeConfig)
class ProgrammeConfigAdmin(admin.ModelAdmin):
    """Only the administrative levels and the CDD module are edited here; the other settings are on
    the dashboard's configuration page, which keeps their history (ConfigChange)."""

    fieldsets = (
        (None, {"fields": ("region_level", "commune_level", "village_level")}),
        ("CDD cycle", {"fields": ("cdd_enabled", "cdd_community_level", "cdd_inactive_days")}),
    )
    list_display = ("__str__", "region_level", "commune_level", "village_level")

    def has_add_permission(self, request):
        return not ProgrammeConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
