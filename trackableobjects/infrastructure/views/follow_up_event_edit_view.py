import json
from django.views.generic.edit import UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext as _
from trackableobjects.models import FollowUpEvent, TrackableObject
from trackableobjects.infrastructure.forms.follow_up_event_create_form import FollowUpEventForm
from django.contrib.auth.mixins import LoginRequiredMixin
from src.permissions import IsStaffMemberMixin
from administrativelevels.models import AdministrativeLevel


class FollowUpEventUpdateView(LoginRequiredMixin, IsStaffMemberMixin, UpdateView):
    """
    Update view for editing existing FollowUpEvents.
    Reuses the same logic as CreateView.
    """
    model = FollowUpEvent
    form_class = FollowUpEventForm
    template_name = "trackable_objects/follow_up_event_create_edit.html"
    extra_context = {
        'title': _('Edit Follow Up Event'),
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update({
            'follow_up_event_objects': self.model.objects.all(),
            'trackable_objects': TrackableObject.objects.all(),
            'administrative_levels': AdministrativeLevel.objects.all().order_by('order'),
        })

        # NEW: Pass ALL available schemas for dynamic loading
        context['all_follow_up_event_schemas_json'] = self.get_all_follow_up_event_schemas_json()
        context['all_trackable_object_schemas_json'] = self.get_all_trackable_object_schemas_json()

        # Serialize the jsonForm for JavaScript (convert Python dict to JSON string)
        context['object'].jsonForm = json.dumps(context['object'].jsonForm)

        return context

    def get_all_follow_up_event_schemas_json(self):
        """
        Get ALL FollowUpEvent schemas as a JSON object
        """
        schemas = {}

        for event in FollowUpEvent.objects.all():
            if event.jsonForm:
                schemas[str(event.id)] = {
                    'id': event.id,
                    'name': event.name,
                    'schema': event.jsonForm
                }

        return json.dumps(schemas)

    def get_all_trackable_object_schemas_json(self):
        """
        Get ALL TrackableObject schemas as a JSON object
        """
        schemas = {}

        for obj in TrackableObject.objects.all():
            if obj.jsonForm:
                schemas[str(obj.id)] = {
                    'id': obj.id,
                    'name': obj.name,
                    'schema': obj.jsonForm
                }

        return json.dumps(schemas)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Your Follow Up Event was successfully updated.'))
        return response

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            "user": self.request.user,
            "trackable_object": self.kwargs.get('pk', None),
        })
        return kwargs

    def get_success_url(self):
        return reverse_lazy("trackableobjects:follow_up_event_object_detail", args=[self.object.pk])
