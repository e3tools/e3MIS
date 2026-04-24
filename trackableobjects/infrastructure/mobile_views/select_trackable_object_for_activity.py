from django.views.generic import TemplateView
from django.db.models import Q, F, Count, Sum, OuterRef, Exists

from src.permissions import IsFieldAgentUserMixin
from trackableobjects.models import (
    TrackableObject, TrackableObjectInstance,
    FollowUpEvent, FollowUpEventResponse,
)


class SelectTrackableObjectForActivityView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'trackable_objects/mobile/select_trackable_object_for_activity.html'

    def get_context_data(self, **kwargs):
        user = self.request.user
        user_group_ids = list(user.groups.values_list('id', flat=True))

        # All admin-unit IDs the user can access (assigned + descendants + ancestors)
        admin_unit_ids = set()
        for unit in user.administrative_units.all():
            self._collect_ancestor_ids(unit, admin_unit_ids)
            self._collect_descendant_ids(unit, admin_unit_ids)

        # ── Trackable objects the user has group access to ───────────────
        matched_groups = TrackableObject.groups.through.objects.filter(
            trackableobject_id=OuterRef('pk'),
            group_id__in=user_group_ids,
        )
        trackable_objects = TrackableObject.objects.filter(Exists(matched_groups))

        # ── Per-object instance + pending counts ────────────────────────
        trackable_objects_data = []
        total_pending = 0

        for to in trackable_objects:
            instances = TrackableObjectInstance.objects.filter(
                Q(restrict_by_administrative_units=False) |
                Q(administrative_units__id__in=admin_unit_ids),
                trackable_object=to,
            ).distinct()

            instance_count = instances.count()

            pending = instances.annotate(
                total_one_off=Count(
                    'trackable_object__follow_up_events',
                    filter=Q(trackable_object__follow_up_events__is_one_off=True),
                    distinct=True,
                ),
                total_responses=Count(
                    'follow_up_responses',
                    filter=Q(follow_up_responses__follow_up_event__is_one_off=True),
                    distinct=True,
                ),
            ).annotate(
                pending_one_off=F('total_one_off') - F('total_responses'),
            ).aggregate(
                pending_total=Sum('pending_one_off'),
            )['pending_total'] or 0

            total_pending += pending

            trackable_objects_data.append({
                'object': to,
                'instance_count': instance_count,
                'pending_count': pending,
            })

        # Sort by most pending first
        trackable_objects_data.sort(key=lambda x: x['pending_count'], reverse=True)

        kwargs['trackable_objects_data'] = trackable_objects_data

        # ── Standalone (global) follow-up events ────────────────────────
        unmatched_fe_groups = FollowUpEvent.groups.through.objects.filter(
            followupevent_id=OuterRef('pk'),
        ).exclude(group_id__in=user_group_ids)

        standalone_events = FollowUpEvent.objects.filter(
            trackable_objects=None,
            is_active=True,
        ).annotate(
            has_unmatched_groups=Exists(unmatched_fe_groups),
        ).filter(has_unmatched_groups=False)

        kwargs['standalone_follow_up_events'] = standalone_events
        kwargs['standalone_count'] = standalone_events.count()

        # Pending global count (one-off events without a response from this user)
        standalone_pending = 0
        for event in standalone_events.filter(is_one_off=True):
            if not FollowUpEventResponse.objects.filter(
                follow_up_event=event, created_by=user,
            ).exists():
                standalone_pending += 1
        kwargs['standalone_pending'] = standalone_pending
        kwargs['total_pending'] = total_pending + standalone_pending

        return super().get_context_data(**kwargs)

    @staticmethod
    def _collect_ancestor_ids(unit, id_set):
        node = unit
        while node is not None:
            id_set.add(node.id)
            node = node.parent

    @staticmethod
    def _collect_descendant_ids(unit, id_set):
        id_set.add(unit.id)
        for child in unit.children.all():
            SelectTrackableObjectForActivityView._collect_descendant_ids(child, id_set)
