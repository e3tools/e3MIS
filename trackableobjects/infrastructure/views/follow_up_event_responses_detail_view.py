from django.views.generic import DetailView
from django.utils.translation import gettext as _

from subprojects.models import Attachment
from trackableobjects.models import FollowUpEventResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from src.permissions import IsStaffMemberMixin
from utils.json_form_parser import parse_custom_jsonschema


class FollowUpEventResponseDetailView(LoginRequiredMixin, IsStaffMemberMixin, DetailView):
    model = FollowUpEventResponse
    template_name = "trackable_objects/response_detail.html"
    extra_context = {
        'title': 'Response Detail',
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '{}: {}'.format(self.object.follow_up_event.name, _('Follow Up Responses Detail'))
        context['form'] = self.get_custom_form()
        context['attachments'] = Attachment.objects.filter(follow_up_event_response=self.object)
        return context

    def get_custom_form(self):
        try:
            follow_up_event = self.object.follow_up_event
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
        except FollowUpEventResponse.DoesNotExist:
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
