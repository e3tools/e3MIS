from django.views.generic.detail import DetailView
from trackableobjects.models import FollowUpEvent

from src.permissions import IsFieldAgentUserMixin


class MobileViewsFollowUpEventDetailView(IsFieldAgentUserMixin, DetailView):
    template_name = 'trackable_objects/mobile/follow_up_event_resp_list.html'
    queryset = FollowUpEvent.objects.all()
    pk_url_kwarg = 'follow_up_event'

    def filter_queryset(self, queryset):
        query = queryset.filter(trackable_object__id=self.kwargs['trackable_instance'])
        return super().filter_queryset(query)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['trackable_instance_id'] = self.kwargs['trackable_instance']
        context['responses'] = self.object.responses.filter(
            trackable_object_instance__id=self.kwargs['trackable_instance'])
        return context
