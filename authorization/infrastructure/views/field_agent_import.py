from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext as _
from django.views.generic import TemplateView

from authorization.agent_import import importer
from authorization.agent_import.reader import read_file, sort_problems
from authorization.agent_import.sheets import MAX_AGENTS
from authorization.infrastructure.forms.field_agent_import_form import (
    FieldAgentImportFileForm, FieldAgentImportPasswordForm,
)
from fieldmonitoring.core.geography import levels_configured
from src.permissions import IsDjangoAdminMixin


class FieldAgentImportView(LoginRequiredMixin, IsDjangoAdminMixin, TemplateView):
    """Step 1: upload the completed template. Every agent is checked as the creation would do it;
    errors are listed, otherwise the preview and the password form are shown (step 2,
    FieldAgentImportConfirmView). The file's content waits in the session in between."""

    template_name = 'auth/field_agent_import.html'
    session_key = 'field_agent_import'

    def get_context_data(self, **kwargs):
        kwargs.setdefault('file_form', FieldAgentImportFileForm())
        kwargs['title'] = _('Import field agents')
        kwargs['levels_configured'] = levels_configured()
        kwargs['max_agents'] = MAX_AGENTS
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        request.session.pop(self.session_key, None)
        file_form = FieldAgentImportFileForm(request.POST, request.FILES)
        if not levels_configured() or not file_form.is_valid():
            return self.render_to_response(self.get_context_data(file_form=file_form))
        agents, errors = read_file(file_form.cleaned_data['file'])
        if errors and not agents:
            return self.render_to_response(self.get_context_data(errors=errors))
        return self.preview(agents, file_errors=errors)

    def preview(self, agents, password_form=None, file_errors=()):
        results, errors = importer.run(agents)
        errors = sort_problems([*file_errors, *errors])
        if errors:
            self.request.session.pop(self.session_key, None)
            return self.render_to_response(self.get_context_data(errors=errors))
        self.request.session[self.session_key] = agents
        return self.render_to_response(self.get_context_data(
            results=results, password_form=password_form or FieldAgentImportPasswordForm(),
        ))
