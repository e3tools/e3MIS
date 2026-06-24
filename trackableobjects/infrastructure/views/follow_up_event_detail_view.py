from django.views.generic import DetailView
from django.utils.translation import gettext as _
from django.contrib import messages
from trackableobjects.models import FollowUpEvent
from administrativelevels.models import AdministrativeLevel, AdministrativeUnit
from django.contrib.auth.mixins import LoginRequiredMixin
from src.permissions import IsStaffMemberMixin
from utils.json_form_parser import parse_custom_jsonschema, schema_requires_assigned_units
from utils.submission_table import build_submission_table


class FollowUpEventDetailView(LoginRequiredMixin, IsStaffMemberMixin, DetailView):
    model = FollowUpEvent
    template_name = "trackable_objects/follow_up_event_detail.html"
    extra_context = {
        'title': 'Follow Up Event Detail',
    }

    def post(self, request, *args, **kwargs):
        """Validate the preview form (client + server) without ever saving it."""
        self.object = self.get_object()
        form = self.get_custom_form()
        if form.is_valid():
            messages.info(request, _("Form is valid — preview only, nothing was saved."))
        # No save path: form_valid is intentionally a no-op for the preview.
        self._bound_form = form
        return self.render_to_response(self.get_context_data())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '{} {}'.format(self.object.name, _(' Detail'))
        context['form'] = getattr(self, '_bound_form', None) or self.get_custom_form()
        responses = self.object.responses.select_related('created_by').prefetch_related('attachments')
        schema_fields, submission_rows = build_submission_table(self.object.jsonForm, responses)
        context['schema_fields'] = schema_fields
        context['submission_rows'] = submission_rows
        # Event-level columns (constant across rows): the event's own groups and
        # the parent events this one depends on (FollowUpEventDependency child=self).
        context['event_groups'] = self.object.groups.all()
        context['depends_on'] = [dep.parent for dep in self.object.dependencies_children.select_related('parent')]
        context['administrative_levels'] = AdministrativeLevel.objects.all().order_by('order')
        return context

    def get_custom_form(self):
        try:
            follow_up_event = self.object
            schema_json = follow_up_event.jsonForm if follow_up_event else {
                "form": [
                    {
                        "page": {
                            "properties": {},
                            "required": []
                        }
                    }
                ]
            }
        except FollowUpEvent.DoesNotExist:
            schema_json = {
                "form": [
                    {
                        "page": {
                            "properties": {},
                            "required": []
                        }
                    }
                ]
            }

        admin_level_ids = []
        if schema_requires_assigned_units(schema_json):
            admin_level_ids = AdministrativeUnit.get_descendant_ids(
                self.request.user.administrative_units.values_list('id', flat=True)
            )

        form_class = parse_custom_jsonschema(
            schema_json, page_index=0,
            administrative_level_ids=admin_level_ids
        )

        return form_class(**self.get_form_kwargs())

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            "initial": {},
            "prefix": '',
        }

        if self.request.method in ("POST", "PUT"):
            kwargs.update(
                {
                    "data": self.request.POST,
                    "files": self.request.FILES,
                }
            )
        return kwargs
