from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.utils import timezone
from django.views import View

from administrativelevels.unit_import.template import build_template
from src.permissions import IsDjangoAdminMixin

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class AdministrativeUnitImportTemplateView(LoginRequiredMixin, IsDjangoAdminMixin, View):
    """The unit import template, with the current tree filled in."""

    def get(self, request, *args, **kwargs):
        response = HttpResponse(build_template(), content_type=XLSX)
        filename = f"administrative_units_{timezone.localdate():%Y%m%d}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
