from django.views.generic.detail import DetailView
from trackableobjects.models import FollowUpEvent

from src.permissions import IsFieldAgentUserMixin


class MobileViewsFollowUpEventDetailView(IsFieldAgentUserMixin, DetailView):
    template_name = 'trackable_objects/mobile/follow_up_event_resp_list.html'
    queryset = FollowUpEvent.objects.all()
