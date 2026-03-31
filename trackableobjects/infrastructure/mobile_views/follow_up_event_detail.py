from django.views.generic.detail import DetailView
from django.db.models import OuterRef, Exists
from trackableobjects.models import FollowUpEvent

from src.permissions import IsFieldAgentUserMixin


class MobileViewsFollowUpEventDetailView(IsFieldAgentUserMixin, DetailView):
    template_name = 'trackable_objects/mobile/follow_up_event_resp_list.html'
    queryset = FollowUpEvent.objects.all()
    pk_url_kwarg = 'follow_up_event'

    def get_queryset(self):
        user_group_ids = list(self.request.user.groups.values_list('id', flat=True))

        unmatched_groups = FollowUpEvent.groups.through.objects.filter(
            followupevent_id=OuterRef('pk')
        ).exclude(
            group_id__in=user_group_ids
        )

        return FollowUpEvent.objects.annotate(
            has_unmatched_groups=Exists(unmatched_groups)
        ).filter(
            has_unmatched_groups=False
        )

    def filter_queryset(self, queryset):
        query = queryset.filter(trackable_object__id=self.kwargs['trackable_instance'])
        return super().filter_queryset(query)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['trackable_instance_id'] = self.kwargs['trackable_instance']
        context['responses'] = self.object.responses.filter(
            trackable_object_instance__id=self.kwargs['trackable_instance'])
        return context
