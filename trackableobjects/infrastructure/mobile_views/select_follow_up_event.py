from django.views.generic import TemplateView
from django.db.models import OuterRef, Exists
from src.permissions import IsFieldAgentUserMixin
from trackableobjects import visibility
from trackableobjects.models import (
    FollowUpEventResponse,
    FollowUpEventTrackableObject,
    TrackableObjectInstance,
)


class SelectFollowUpEventView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'trackable_objects/mobile/select_follow_up_event.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_group_ids = list(self.request.user.groups.values_list('id', flat=True))

        trackable_object_instance = TrackableObjectInstance.objects.select_related(
            'trackable_object'
        ).get(id=self.kwargs['pk'])

        context['trackable_object_instance'] = trackable_object_instance

        # Get base queryset with all necessary annotations
        follow_up_events_qs = self._get_follow_up_events_queryset(
            user_group_ids,
            trackable_object_instance
        )

        # Split into one-off and repeating events
        context['one_off_follow_up_events'] = follow_up_events_qs.filter(is_one_off=True)
        context['repeating_follow_up_events'] = follow_up_events_qs.filter(is_one_off=False)

        # Annotate one-off events with response status
        self._annotate_response_status(
            context['one_off_follow_up_events'],
            trackable_object_instance
        )

        # Annotate repeating events with response count
        self._annotate_response_count(
            context['repeating_follow_up_events'],
            trackable_object_instance
        )

        return context

    def _get_follow_up_events_queryset(self, user_group_ids, trackable_object_instance):
        """Events the user can fill on this record now (shared rule, see trackableobjects.visibility)."""
        has_trackable_objects = FollowUpEventTrackableObject.objects.filter(follow_up_event=OuterRef('pk'))
        return visibility.available_follow_up_events(self.request.user, trackable_object_instance).annotate(
            is_global=~Exists(has_trackable_objects),
        )

    def _annotate_response_status(self, follow_up_events, trackable_object_instance):
        """Adds has_no_response and response_id attributes to one-off events."""
        for follow_up_event in follow_up_events:
            response = FollowUpEventResponse.objects.filter(
                follow_up_event=follow_up_event,
                trackable_object_instance=trackable_object_instance
            ).first()

            follow_up_event.has_no_response = response is None
            follow_up_event.response_id = response.id if response else None

    @staticmethod
    def _annotate_response_count(follow_up_events, trackable_object_instance):
        """Adds response_count attribute to repeating events."""
        for event in follow_up_events:
            event.response_count = FollowUpEventResponse.objects.filter(
                follow_up_event=event,
                trackable_object_instance=trackable_object_instance,
            ).count()
