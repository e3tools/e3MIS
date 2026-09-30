from django.contrib import admin

from fieldmonitoring.registry.admin import ReadOnlyAdmin

from .models import ConfigChange, JobRun


@admin.register(ConfigChange)
class ConfigChangeAdmin(ReadOnlyAdmin):
    list_display = ("key", "old_value", "new_value", "changed_by", "changed_at")


@admin.register(JobRun)
class JobRunAdmin(ReadOnlyAdmin):
    list_display = ("job", "run_key", "ran_at")
