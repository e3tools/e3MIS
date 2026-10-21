from django.contrib import admin

from fieldmonitoring.registry.admin import ReadOnlyAdmin

from .models import Visit, VisitEvent, VisitFlag


class EventInline(admin.TabularInline):
    model = VisitEvent
    extra = 0
    can_delete = False
    readonly_fields = ("event", "from_state", "to_state", "reason", "actor", "at", "note")

    def has_add_permission(self, request, obj=None):
        return False


class FlagInline(admin.TabularInline):
    model = VisitFlag
    extra = 0
    can_delete = False
    readonly_fields = ("kind", "detail", "raised_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Visit)
class VisitAdmin(ReadOnlyAdmin):
    """Read-only. State changes only happen through the state machine."""

    list_display = ("user", "worksite", "state", "unverified_reason", "checked_in_at", "time_on_site_s")
    list_filter = ("state", "unverified_reason", "auto_closed")
    search_fields = ("user__full_name", "worksite__name")
    inlines = [EventInline, FlagInline]
