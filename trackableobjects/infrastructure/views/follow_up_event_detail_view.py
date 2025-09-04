from django.views.generic import DetailView
from django.utils.translation import gettext as _
from trackableobjects.models import FollowUpEvent
from django.contrib.auth.mixins import LoginRequiredMixin
from src.permissions import IsStaffMemberMixin
from utils.json_form_parser import parse_custom_jsonschema


class FollowUpEventDetailView(LoginRequiredMixin, IsStaffMemberMixin, DetailView):
    model = FollowUpEvent
    template_name = "trackable_objects/follow_up_event_detail.html"
    extra_context = {
        'title': 'Follow Up Event Detail',
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '{} {}'.format(self.object.name, _(' Detail'))
        context['form'] = self.get_custom_form()
        context['responses'] = self.object.responses.all()
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

        form_class = parse_custom_jsonschema(schema_json, page_index=0)

        return form_class(**self.get_form_kwargs())

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            "initial": {},
            "prefix": '',
        }
        return kwargs
