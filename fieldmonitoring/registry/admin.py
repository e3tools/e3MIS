from django import forms
from django.contrib import admin, messages
from django.contrib.gis.admin import GISModelAdmin
from django.shortcuts import redirect, render
from django.urls import path

from .importer import import_worksites
from .models import (
    HighRiskFlagChange,
    ProvisionalCoordinate,
    Worksite,
    WorksiteAssignment,
)


class CsvImportForm(forms.Form):
    file = forms.FileField(help_text="name, code, village, commune, region, latitude, longitude, tolerance_m, status")


@admin.register(Worksite)
class WorksiteAdmin(GISModelAdmin):
    list_display = ("name", "code", "village", "commune", "status", "has_coordinate", "is_high_risk")
    list_filter = ("status", "is_high_risk", "is_provisional", "region", "commune")
    search_fields = ("name", "code", "village__name")
    # The high-risk flag has rules admin cannot enforce (BR-15): use the approval screen.
    readonly_fields = ("is_high_risk", "high_risk_review_due_on", "created_by", "created_at")
    change_list_template = "admin/registry/worksite/change_list.html"

    @admin.display(boolean=True, description="Coordinate")
    def has_coordinate(self, obj):
        return obj.location is not None

    def get_urls(self):
        return [path("import-csv/", self.admin_site.admin_view(self.import_csv), name="worksite_import")] + super().get_urls()

    def import_csv(self, request):
        form = CsvImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            result = import_worksites(form.cleaned_data["file"].read().decode("utf-8"))
            if result.errors:
                for err in result.errors[:20]:
                    messages.error(request, err)
            else:
                messages.success(request, f"{result.created} created, {result.updated} updated.")
                return redirect("admin:registry_worksite_changelist")
        return render(
            request,
            "admin/registry/worksite/import.html",
            {**self.admin_site.each_context(request), "form": form, "title": "Import worksites"},
        )


@admin.register(WorksiteAssignment)
class WorksiteAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "worksite", "assigned_on", "unassigned_on")
    list_filter = ("unassigned_on",)
    autocomplete_fields = ("user", "worksite")

    def has_delete_permission(self, request, obj=None):
        return False  # set unassigned_on instead (Story 1.4)


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HighRiskFlagChange)
class HighRiskFlagChangeAdmin(ReadOnlyAdmin):
    list_display = ("worksite", "to_value", "status", "proposed_by", "approved_by", "review_due_on")


@admin.register(ProvisionalCoordinate)
class ProvisionalCoordinateAdmin(ReadOnlyAdmin):
    list_display = ("worksite", "captured_by", "captured_at", "status")
