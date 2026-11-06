from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.utils import timezone
from django.views import View

from authorization.agent_import.template import build_template
from src.permissions import IsDjangoAdminMixin

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class FieldAgentImportTemplateView(LoginRequiredMixin, IsDjangoAdminMixin, View):
    """The agent import template, built from the current groups, units and SCs."""

    def get(self, request, *args, **kwargs):
        response = HttpResponse(build_template(), content_type=XLSX)
        filename = f"field_agents_{timezone.localdate():%Y%m%d}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
