from django.urls import reverse
from django.views.generic import DetailView
from django.utils.translation import gettext as _

from subprojects.models import Attachment
from trackableobjects.models import TrackableObjectInstance
from administrativelevels.models import AdministrativeLevel
from django.contrib.auth.mixins import LoginRequiredMixin
from src.permissions import IsStaffMemberMixin
from utils.json_form_parser import parse_custom_jsonschema
from trackableobjects.infrastructure.views.editable_submission_mixin import EditableSubmissionMixin

EMPTY_SCHEMA = {"form": [{"page": {"properties": {}, "required": []}}]}


class TrackableObjectInstanceDetailView(EditableSubmissionMixin, LoginRequiredMixin, IsStaffMemberMixin, DetailView):
    model = TrackableObjectInstance
    template_name = "trackable_objects/response_detail.html"
    extra_context = {
        'title': 'Response Detail',
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '{}: {}'.format(self.object.trackable_object.name, _('Trackable Object Detail'))
        context['form'] = getattr(self, '_bound_form', None) or self.get_custom_form()
        context['attachments'] = Attachment.objects.filter(trackable_object_instance=self.object)
        context['administrative_levels'] = AdministrativeLevel.objects.all().order_by('order')
        context.setdefault('editing', False)
        return context

    def get_schema_json(self):
        return self.object.trackable_object.jsonForm

    def get_success_url(self):
        return reverse('trackableobjects:trackable_object_instance_detail', kwargs={'pk': self.object.pk})

    def get_custom_form(self):
        schema_json = self.get_schema_json() or EMPTY_SCHEMA
        form_class = parse_custom_jsonschema(
            schema_json, page_index=0,
            administrative_level_ids=self.get_admin_level_ids(),
        )
        return form_class(**self.get_form_kwargs())

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
