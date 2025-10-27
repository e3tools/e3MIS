from django.views.generic.edit import CreateView, FormView
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext as _
from trackableobjects.models import FollowUpEvent, TrackableObject
from trackableobjects.infrastructure.forms.follow_up_event_create_form import FollowUpEventForm
from django.contrib.auth.mixins import LoginRequiredMixin
from src.permissions import IsStaffMemberMixin


class FollowUpEventCreateView(LoginRequiredMixin, IsStaffMemberMixin, CreateView):
    model = FollowUpEvent
    form_class = FollowUpEventForm
    template_name = "trackable_objects/follow_up_event_create_edit.html"

    def get_context_data(self, **kwargs):
        kwargs.update({
            'follow_up_event_objects': self.model.objects.all(),
            'trackable_objects': TrackableObject.objects.all(),
        })
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Your Follow Up Event was successfully created or updated.'))
        return response

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            "user": self.request.user,
            "trackable_object": self.kwargs.get('pk', None),
        })
        return kwargs

    def get_success_url(self):
        if 'pk' in self.kwargs:
            return reverse_lazy("trackableobjects:trackable_object_detail", args=[self.kwargs['pk']])
        return reverse_lazy("trackableobjects:follow_up_event_list")
