from django.views.generic import TemplateView
from django.core.exceptions import PermissionDenied
from django.db.models import Q, OuterRef, Subquery, Exists, Value, IntegerField
from src.permissions import IsFieldAgentUserMixin
from trackableobjects.models import (
    FollowUpEvent,
    FollowUpEventResponse,
    FollowUpEventTrackableObject,
    TrackableObjectInstance,
    FollowUpEventDependency
)


class SelectFollowUpEventView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'trackable_objects/mobile/select_follow_up_event.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_group_ids = list(self.request.user.groups.values_list('id', flat=True))

        trackable_object_instance = TrackableObjectInstance.objects.select_related(
            'trackable_object'
        ).get(id=self.kwargs['pk'])

        # Verify user shares at least one group with the parent TrackableObject
        trackable_object_groups = trackable_object_instance.trackable_object.groups.all()
        if trackable_object_groups.exists() and not self.request.user.groups.filter(
            id__in=trackable_object_groups
        ).exists():
            raise PermissionDenied

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

        return context

    def _get_follow_up_events_queryset(self, user_group_ids, trackable_object_instance):
        """Returns queryset of FollowUpEvents filtered by permissions and dependencies."""

        # Subquery: groups on this event that the user is NOT in
        unmatched_groups = FollowUpEvent.groups.through.objects.filter(
            followupevent_id=OuterRef('pk')
        ).exclude(
            group_id__in=user_group_ids
        )

        # Subquery: Check for unfulfilled parent dependencies
        unfulfilled_dependencies = FollowUpEventDependency.objects.filter(
            child_id=OuterRef('pk')
        ).exclude(
            parent_id__in=Subquery(
                FollowUpEventResponse.objects.filter(
                    trackable_object_instance=trackable_object_instance
                ).values('follow_up_event_id')
            )
        )

        # Subquery: get order from through table for this trackable object
        through_order = FollowUpEventTrackableObject.objects.filter(
            follow_up_event=OuterRef('pk'),
            trackable_object=trackable_object_instance.trackable_object
        ).values('order')[:1]

        return FollowUpEvent.objects.annotate(
            has_unmatched_groups=Exists(unmatched_groups),
            has_unfulfilled_deps=Exists(unfulfilled_dependencies),
            custom_order=Subquery(through_order, output_field=IntegerField()),
        ).filter(
            # Event applies to this trackable object
            Q(trackable_objects=trackable_object_instance.trackable_object) | Q(trackable_objects=None),
            # User has permission (no groups the user isn't in)
            has_unmatched_groups=False,
            # Event is active and has no unfulfilled dependencies
            is_active=True,
            has_unfulfilled_deps=False
        ).distinct().order_by('custom_order', 'name')

    def _annotate_response_status(self, follow_up_events, trackable_object_instance):
        """Adds has_no_response and response_id attributes to one-off events."""
        for follow_up_event in follow_up_events:
            response = FollowUpEventResponse.objects.filter(
                follow_up_event=follow_up_event,
                trackable_object_instance=trackable_object_instance
            ).first()

            follow_up_event.has_no_response = response is None
            follow_up_event.response_id = response.id if response else None
