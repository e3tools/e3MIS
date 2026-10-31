"""Django admin for the CDD cycle until the MIS designer exists (build plan step 2)."""
from django.contrib import admin

from . import progress
from .models import Activity, Cycle, CycleEvent, CycleTemplate, Phase, Task, TaskForm, TaskProgress


class PhaseInline(admin.TabularInline):
    model = Phase
    extra = 0
    fields = ("order", "name", "planned_days")
    show_change_link = True


@admin.register(CycleTemplate)
class CycleTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "is_active", "updated_at")
    readonly_fields = ("version",)
    inlines = [PhaseInline]


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0
    fields = ("order", "name")
    show_change_link = True


@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ("name", "template", "order", "planned_days")
    list_filter = ("template",)
    inlines = [ActivityInline]


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ("order", "key", "name", "kind", "required", "planned_offset_days")
    show_change_link = True


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("name", "phase", "order")
    list_filter = ("phase__template",)
    inlines = [TaskInline]


class TaskFormInline(admin.TabularInline):
    model = TaskForm
    extra = 0


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "activity", "kind", "required", "planned_offset_days")
    list_filter = ("activity__phase__template", "kind")
    search_fields = ("key", "name")
    filter_horizontal = ("depends_on",)
    inlines = [TaskFormInline]


class TaskProgressInline(admin.TabularInline):
    model = TaskProgress
    extra = 0
    fields = ("task_key", "manual_status", "note", "decided_by", "decided_at")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class CycleEventInline(admin.TabularInline):
    model = CycleEvent
    extra = 0
    fields = ("at", "kind", "task_key", "by", "note")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Cycle)
class CycleAdmin(admin.ModelAdmin):
    """Read-mostly: start, close and reopen go through cdd/services.py (the designer, step 2)."""

    list_display = ("community", "number", "template", "status", "started_on", "progress_display")
    list_filter = ("status", "template")
    search_fields = ("community__name",)
    readonly_fields = ("template", "template_version", "community", "number", "status", "progress_display")
    fields = ("template", "template_version", "community", "number", "status", "started_on", "planned_end",
              "facilitators", "progress_display")
    filter_horizontal = ("facilitators",)
    inlines = [TaskProgressInline, CycleEventInline]

    def has_add_permission(self, request):
        return False

    @admin.display(description="Progress")
    def progress_display(self, obj):
        value = progress.state(obj).progress
        return "-" if value is None else f"{round(value * 100)} %"
