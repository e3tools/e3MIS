from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _, ngettext

from administrativelevels.infrastructure.views.unit_import import AdministrativeUnitImportView
from administrativelevels.unit_import import importer


class AdministrativeUnitImportConfirmView(AdministrativeUnitImportView):
    """Step 2: creates the missing units and sets the zones, all or nothing. The rows are matched
    again, since the tree may have changed since step 1."""

    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        rows = request.session.get(self.session_key)
        if not rows:
            messages.warning(request, _('Upload the file again: the checked file was not found.'))
            return redirect('administrativelevels:administrative_unit_import')
        summary, errors = importer.run(rows, commit=True)
        request.session.pop(self.session_key, None)
        if errors:
            return self.render_to_response(self.get_context_data(errors=errors, changed=True))
        created = len(summary['new_units'])
        messages.success(request, ngettext(
            '%(count)s administrative unit created.', '%(count)s administrative units created.', created
        ) % {'count': created})
        if summary['zones']:
            messages.info(request, ngettext(
                'Zone set for %(count)s village.', 'Zone set for %(count)s villages.', summary['zones']
            ) % {'count': summary['zones']})
        if summary['radii']:
            messages.info(request, ngettext(
                'The radius of %(count)s worksite follows its new zone.',
                'The radius of %(count)s worksites follows their new zone.', summary['radii'],
            ) % {'count': summary['radii']})
        return redirect('administrativelevels:administrative_unit_root')
