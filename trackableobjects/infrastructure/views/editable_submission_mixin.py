from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.translation import gettext as _

from utils.dynamic_form_io import build_json_form
from utils.submission_table import extract_schema_fields


class EditableSubmissionMixin:
    """In-place editing of a dynamic-form submission's answers.

    Mixed into the read-only ``DetailView``s for ``TrackableObjectInstance`` and
    ``FollowUpEventResponse``. The host view must provide ``get_custom_form()``,
    ``get_schema_json()`` and ``get_success_url()``.

    File answers stay read-only: their fields are excluded from validation and
    preserved verbatim on save, so existing attachments are never touched.
    """

    def get_file_field_names(self):
        return {
            field['name']
            for field in extract_schema_fields(self.get_schema_json())
            if field['type'] == 'file'
        }

    def relax_file_fields(self, form):
        """Read-only file fields must never block a save."""
        for name in self.get_file_field_names():
            if name in form.fields:
                form.fields[name].required = False

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_custom_form()
        self.relax_file_fields(form)
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        new_data = build_json_form(form)
        file_fields = self.get_file_field_names()
        merged = dict(self.object.jsonForm) if isinstance(self.object.jsonForm, dict) else {}
        for key, value in new_data.items():
            if key in file_fields:
                continue  # preserve the stored 'Attachment' marker and its file
            merged[key] = value
        self.object.jsonForm = merged
        self.object.save()
        messages.success(self.request, _('Answers updated successfully.'))
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        self._bound_form = form
        context = self.get_context_data()
        context['editing'] = True
        return self.render_to_response(context)
