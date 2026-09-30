from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import DeleteView
from django.urls import reverse_lazy

from src.permissions import IsAdminMemberMixin

from trackableobjects.models import FollowUpEvent


class FollowUpEventDeleteView(LoginRequiredMixin, IsAdminMemberMixin, DeleteView):
    model = FollowUpEvent
    success_url = reverse_lazy("trackableobjects:follow_up_event_list")
