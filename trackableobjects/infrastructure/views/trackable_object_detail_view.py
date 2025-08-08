from django.views.generic import DetailView
from django.utils.translation import gettext as _
from trackableobjects.models import TrackableObject
from trackableobjects.infrastructure.forms.trackable_object_create_form import TrackableObjectForm
from django.contrib.auth.mixins import LoginRequiredMixin
from src.permissions import IsStaffMemberMixin
from utils.json_form_parser import parse_custom_jsonschema


class TrackableObjectDetailView(LoginRequiredMixin, IsStaffMemberMixin, DetailView):
    model = TrackableObject
    form_class = TrackableObjectForm
    template_name = "trackable_objects/detail.html"
    extra_context = {
        'title': 'Trackable Object Detail',
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '{}: {}'.format(self.object.name, _('Trackable Object Detail'))
        context['form'] = self.get_custom_form()
        context['responses'] = self.object.responses.all()
        return context

    def get_custom_form(self):
        try:
            trackable_object = self.object
            schema_json = trackable_object.jsonForm if trackable_object else {
                "form": [
                    {
                        "page": {
                            "properties": {},
                            "required": []
                        }
                    }
                ]
            }
        except TrackableObject.DoesNotExist:
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

        form_class = parse_custom_jsonschema(schema_json, page_index=0)

        return form_class(**self.get_form_kwargs())

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            "initial": {},
            "prefix": '',
        }
        return kwargs
