from django.views.generic import DetailView
from django.utils.translation import gettext as _

from subprojects.models import Attachment
from trackableobjects.models import TrackableObjectResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from src.permissions import IsStaffMemberMixin
from utils.json_form_parser import parse_custom_jsonschema


class TrackableObjectResponseDetailView(LoginRequiredMixin, IsStaffMemberMixin, DetailView):
    model = TrackableObjectResponse
    template_name = "trackable_objects/response_detail.html"
    extra_context = {
        'title': 'Response Detail',
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '{}: {}'.format(self.object.trackable_object.name, _('Trackable Object Detail'))
        context['form'] = self.get_custom_form()
        context['attachments'] = Attachment.objects.filter(trackable_object_response=self.object)
        return context

    def get_custom_form(self):
        try:
            trackable_object = self.object.trackable_object
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
        except TrackableObjectResponse.DoesNotExist:
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
            "initial": self.object.jsonForm if self.object else {},
            "prefix": '',
        }
        return kwargs
