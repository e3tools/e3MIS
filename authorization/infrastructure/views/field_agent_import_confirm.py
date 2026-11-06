from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _, ngettext

from authorization.agent_import import importer
from authorization.infrastructure.forms.field_agent_import_form import FieldAgentImportPasswordForm
from authorization.infrastructure.views.field_agent_import import FieldAgentImportView


class FieldAgentImportConfirmView(FieldAgentImportView):
    """Step 2: the shared password, then the creation. The agents are checked again, since the
    data may have changed since step 1 (a group deleted, an SC created): all are created or none."""

    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        agents = request.session.get(self.session_key)
        if not agents:
            messages.warning(request, _('Upload the file again: the checked file was not found.'))
            return redirect('authorization:field_agent_import')
        password_form = FieldAgentImportPasswordForm(request.POST)
        if not password_form.is_valid():
            return self.preview(agents, password_form)
        results, errors = importer.run(agents, password=password_form.cleaned_data['password1'], commit=True)
        request.session.pop(self.session_key, None)
        if errors:
            return self.render_to_response(self.get_context_data(errors=errors, changed=True))
        without_supervisor = sum(
            1 for result in results if result['role_code'] in ('ft', 'fc') and not result['supervisor']
        )
        messages.success(request, ngettext(
            '%(count)s field agent created.', '%(count)s field agents created.', len(results)
        ) % {'count': len(results)})
        if without_supervisor:
            messages.info(request, ngettext(
                '%(count)s facilitator has no supervisor yet: their commune has no SC. The SC created later '
                'on this page takes them over.',
                '%(count)s facilitators have no supervisor yet: their commune has no SC. The SC created later '
                'on this page takes them over.',
                without_supervisor,
            ) % {'count': without_supervisor})
        return redirect('authorization:field_agent_list')
