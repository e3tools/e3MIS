from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext as _
from django.views.generic import TemplateView

from administrativelevels.models import AdministrativeLevel
from administrativelevels.unit_import import importer
from administrativelevels.unit_import.reader import read_file
from administrativelevels.unit_import.sheets import MAX_ROWS
from authorization.infrastructure.forms.field_agent_import_form import FieldAgentImportFileForm
from src.permissions import IsDjangoAdminMixin

# New units listed in the preview; the counts per level cover the rest.
PREVIEW_LIMIT = 500


class AdministrativeUnitImportView(LoginRequiredMixin, IsDjangoAdminMixin, TemplateView):
    """Step 1: upload the completed template. The rows are matched against the tree; errors are
    listed, otherwise what will be created is shown with a confirm button
    (AdministrativeUnitImportConfirmView). The rows wait in the session in between."""

    template_name = 'administrative_units/unit_import.html'
    session_key = 'administrative_unit_import'

    def get_context_data(self, **kwargs):
        kwargs.setdefault('file_form', FieldAgentImportFileForm())
        kwargs['title'] = _('Import administrative units')
        kwargs['has_levels'] = AdministrativeLevel.objects.exists()
        kwargs['max_rows'] = MAX_ROWS
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        request.session.pop(self.session_key, None)
        file_form = FieldAgentImportFileForm(request.POST, request.FILES)
        if not AdministrativeLevel.objects.exists() or not file_form.is_valid():
            return self.render_to_response(self.get_context_data(file_form=file_form))
        rows, errors = read_file(file_form.cleaned_data['file'])
        if errors:
            return self.render_to_response(self.get_context_data(errors=errors))
        summary, errors = importer.run(rows)
        if errors:
            return self.render_to_response(self.get_context_data(errors=errors))
        request.session[self.session_key] = rows
        return self.render_to_response(self.get_context_data(
            summary=summary, new_units=summary['new_units'][:PREVIEW_LIMIT],
            more_units=max(0, len(summary['new_units']) - PREVIEW_LIMIT),
            new_total=len(summary['new_units']),
        ))
