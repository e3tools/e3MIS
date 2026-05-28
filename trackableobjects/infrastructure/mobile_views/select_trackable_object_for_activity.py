import json

from django.views.generic import TemplateView
from django.db.models import Q, F, Count, Sum, OuterRef, Exists

from administrativelevels.models import AdministrativeUnit
from src.permissions import IsFieldAgentUserMixin
from authorization.models import AppSettings
from trackableobjects.models import (
    TrackableObject, TrackableObjectInstance,
    FollowUpEvent, FollowUpEventResponse,
    FollowUpEventTrackableObject,
)


class SelectTrackableObjectForActivityView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'trackable_objects/mobile/select_trackable_object_for_activity.html'

    def get_context_data(self, **kwargs):
        user = self.request.user
        user_group_ids = list(user.groups.values_list('id', flat=True))

        # Build full accessible tree (ancestors + assigned units + descendants)
        user_units = list(
            user.administrative_units.all()
            .select_related('level')
        )

        all_units = {}

        def collect_descendants(node):
            if node.id in all_units:
                return
            all_units[node.id] = node
            for child in node.children.select_related('level').order_by('name'):
                collect_descendants(child)

        def collect_ancestors(node):
            current = node.parent
            while current is not None:
                if current.id in all_units:
                    break
                if not hasattr(current, '_level_cache'):
                    current = AdministrativeUnit.objects.select_related('level').get(pk=current.pk)
                all_units[current.id] = current
                current = current.parent

        for unit in user_units:
            collect_descendants(unit)
            collect_ancestors(unit)

        admin_unit_ids = set(all_units.keys())

        # Handle admin_unit query parameter for filtering
        selected_admin_unit = self.request.GET.get('admin_unit', '')
        filtered_unit_ids = admin_unit_ids

        if selected_admin_unit:
            try:
                selected_id = int(selected_admin_unit)
                if selected_id in admin_unit_ids:
                    filtered_ids = set()

                    def collect_subtree(uid):
                        filtered_ids.add(uid)
                        for other_id, other_unit in all_units.items():
                            if other_unit.parent_id == uid:
                                collect_subtree(other_id)

                    collect_subtree(selected_id)
                    filtered_unit_ids = filtered_ids
            except (ValueError, TypeError):
                pass

        # ── FollowUpEvents accessible to this user (at least one shared group) ──
        matched_fe_groups = FollowUpEvent.groups.through.objects.filter(
            followupevent_id=OuterRef('pk'),
            group_id__in=user_group_ids,
        )

        accessible_fe_ids = FollowUpEvent.objects.filter(
            Exists(matched_fe_groups),
            is_active=True,
        ).values('id')

        fe_linked_tos = FollowUpEventTrackableObject.objects.filter(
            follow_up_event_id__in=accessible_fe_ids,
            trackable_object_id=OuterRef('pk'),
        )

        trackable_objects = TrackableObject.objects.filter(
            Exists(fe_linked_tos)
        ).distinct()

        # ── Admin unit tree with instance counts ──────────────────────
        direct_counts = dict(
            TrackableObjectInstance.objects.filter(
                trackable_object__in=trackable_objects,
                administrative_units__id__in=admin_unit_ids,
            ).values_list('administrative_units__id').annotate(
                count=Count('id', distinct=True)
            )
        )

        subtree_cache = {}

        def subtree_count(unit_id):
            if unit_id in subtree_cache:
                return subtree_cache[unit_id]
            count = direct_counts.get(unit_id, 0)
            for uid, u in all_units.items():
                if u.parent_id == unit_id:
                    count += subtree_count(uid)
            subtree_cache[unit_id] = count
            return count

        units_data = []
        for uid, u in all_units.items():
            ic = subtree_count(uid)
            if ic == 0:
                continue
            units_data.append({
                'id': u.id,
                'name': u.name,
                'level_name': u.level.name,
                'parent_id': u.parent_id if u.parent_id in all_units else None,
                'instance_count': ic,
            })

        kwargs['units_json'] = json.dumps(units_data)
        kwargs['selected_admin_unit'] = selected_admin_unit

        # ── Per-object instance + pending counts ────────────────────────
        trackable_objects_data = []
        total_pending = 0

        for to in trackable_objects:
            instances = TrackableObjectInstance.objects.filter(
                Q(restrict_by_administrative_units=False) |
                Q(administrative_units__id__in=filtered_unit_ids),
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
        matched_standalone_groups = FollowUpEvent.groups.through.objects.filter(
            followupevent_id=OuterRef('pk'),
            group_id__in=user_group_ids,
        )

        standalone_events = FollowUpEvent.objects.filter(
            Exists(matched_standalone_groups),
            trackable_objects=None,
            is_active=True,
        )

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
        kwargs['show_all_activities_btn'] = AppSettings.load().show_all_activities_button

        return super().get_context_data(**kwargs)
