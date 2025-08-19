from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext as _
from trackableobjects.models import FollowUpEvent
from trackableobjects.infrastructure.forms.follow_up_event_create_form import FollowUpEventForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from src.permissions import IsStaffMemberMixin


class FollowUpEventCreateView(LoginRequiredMixin, IsStaffMemberMixin, CreateView):
    model = FollowUpEvent
    form_class = FollowUpEventForm
    template_name = "trackable_objects/follow_up_event_create_edit.html"
    success_url = reverse_lazy("trackableobjects:trackable_object_list")

    def get_context_data(self, **kwargs):
        kwargs.update({'follow_up_event_objects': self.model.objects.all()})
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Your Follow Up Event was successfully created or updated.'))
        return response

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            "user": self.request.user,
            "trackable_object": self.kwargs['trackable_object_pk'],
        })
        return kwargs
