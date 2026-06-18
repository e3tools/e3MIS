import json

from django.urls import reverse
from django.views.generic import DetailView
from django.utils.translation import gettext as _

from subprojects.models import Attachment
from trackableobjects.models import FollowUpEventResponse
from administrativelevels.models import AdministrativeLevel
from django.contrib.auth.mixins import LoginRequiredMixin
from src.permissions import IsStaffMemberMixin
from utils.json_form_parser import parse_custom_jsonschema
from utils.dynamic_form_io import serialize_for_json
from trackableobjects.infrastructure.views.editable_submission_mixin import EditableSubmissionMixin

EMPTY_SCHEMA = {"form": [{"page": {"properties": {}, "required": []}}]}


class FollowUpEventResponseDetailView(EditableSubmissionMixin, LoginRequiredMixin, IsStaffMemberMixin, DetailView):
    model = FollowUpEventResponse
    template_name = "trackable_objects/response_detail.html"
    extra_context = {
        'title': 'Response Detail',
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '{}: {}'.format(self.object.follow_up_event.name, _('Follow Up Responses Detail'))
        context['form'] = getattr(self, '_bound_form', None) or self.get_custom_form()
        context['attachments'] = Attachment.objects.filter(follow_up_event_response=self.object)
        context['administrative_levels'] = AdministrativeLevel.objects.all().order_by('order')
        context['parent_form_data_json'] = json.dumps(serialize_for_json(self.get_parent_form_data()))
        context.setdefault('editing', False)
        return context

    def get_schema_json(self):
        return self.object.follow_up_event.jsonForm

    def get_success_url(self):
        return reverse('trackableobjects:follow_up_event_response_detail', kwargs={'pk': self.object.pk})

    def get_custom_form(self):
        schema_json = self.get_schema_json() or EMPTY_SCHEMA
        form_class = parse_custom_jsonschema(
            schema_json, page_index=0,
            administrative_level_ids=self.get_admin_level_ids(),
            parent_form_data=self.get_parent_form_data(),
        )
        return form_class(**self.get_form_kwargs())

    def get_parent_form_data(self):
        """Merge parent-form answers so cross-form conditionals evaluate correctly.

        Sources: the related trackable object instance, plus the most recent
        response to each parent event (events this one depends on) for that
        same instance.
        """
        data = {}
        trackable_object_instance = self.object.trackable_object_instance
        if trackable_object_instance and isinstance(trackable_object_instance.jsonForm, dict):
            data.update(trackable_object_instance.jsonForm)

        for dependency in self.object.follow_up_event.dependencies_children.select_related('parent'):
            if not trackable_object_instance:
                continue
            parent_response = FollowUpEventResponse.objects.filter(
                follow_up_event=dependency.parent,
                trackable_object_instance=trackable_object_instance,
            ).order_by('-created_at').first()
            if parent_response and isinstance(parent_response.jsonForm, dict):
                data.update(parent_response.jsonForm)
        return data

    def get_admin_level_ids(self):
        return [id for unit in self.request.user.administrative_units.all() for id in self.get_descendants(unit)]

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            "initial": self.object.jsonForm if self.object else {},
            "prefix": '',
        }
        if self.request.method in ("POST", "PUT"):
            kwargs.update({
                "data": self.request.POST,
                "files": self.request.FILES,
            })
        return kwargs

    def get_descendants(self, administrative_unit):
        descendants = []

        def recurse(node):
            descendants.append(node.id)
            for child in node.children.all():
                recurse(child)

        recurse(administrative_unit)
        return descendants
