from django.views.generic.edit import DeleteView
from django.urls import reverse_lazy

from trackableobjects.models import FollowUpEvent


class FollowUpEventDeleteView(DeleteView):
    model = FollowUpEvent
    success_url = reverse_lazy("trackableobjects:follow_up_event_list")
