from django.views.generic import TemplateView
from django.db.models import Q, OuterRef, Count, Subquery, IntegerField, F
from src.permissions import IsFieldAgentUserMixin
from trackableobjects.models import FollowUpEvent, FollowUpEventResponse, TrackableObjectInstance


class SelectFollowUpEventView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'trackable_objects/mobile/select_follow_up_event.html'

    def get_context_data(self, **kwargs):
        user_group_ids = list(self.request.user.groups.values_list('id', flat=True))
        kwargs['trackable_object_instance'] = TrackableObjectInstance.objects.filter(id=self.kwargs['pk']).select_related(
            'trackable_object').first()

        matching_group_count = FollowUpEvent.groups.through.objects.filter(
            followupevent_id=OuterRef('pk'),
            group_id__in=user_group_ids
        ).values('followupevent_id').annotate(
            count=Count('group_id')
        ).values('count')

        one_off_follow_up_events = FollowUpEvent.objects.annotate(
                total_groups=Count('groups', distinct=True),
                matched_groups=Subquery(matching_group_count, output_field=IntegerField()),
            ).filter(
                Q(total_groups=0) |
                Q(total_groups=F('matched_groups'))
            ).filter(
                trackable_object=kwargs['trackable_object_instance'].trackable_object,
                is_one_off=True,
                is_active=True
            ).distinct()

        repeating_follow_up_events = FollowUpEvent.objects.annotate(
                total_groups=Count('groups', distinct=True),
                matched_groups=Subquery(matching_group_count, output_field=IntegerField()),
            ).filter(
                Q(total_groups=0) |
                Q(total_groups=F('matched_groups'))
            ).filter(
                trackable_object=kwargs['trackable_object_instance'].trackable_object,
                is_one_off=False,
                is_active=True
            ).distinct()

        kwargs.update({'one_off_follow_up_events': one_off_follow_up_events})
        kwargs.update({'repeating_follow_up_events': repeating_follow_up_events})

        for follow_up_event in kwargs['one_off_follow_up_events']:
            qs = FollowUpEventResponse.objects.filter(
                    follow_up_event=follow_up_event,
                    trackable_object_instance=kwargs['trackable_object_instance']
            )
            if not qs.exists():
                follow_up_event.has_no_response = True
            else:
                follow_up_event.has_no_response = False
                follow_up_event.response_id = qs.first().id

        return super().get_context_data(**kwargs)
