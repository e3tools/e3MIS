from collections import defaultdict

from django.urls import reverse
from django.views.generic import TemplateView
from django.db.models import Q, OuterRef, Exists, Subquery

from src.permissions import IsFieldAgentUserMixin
from trackableobjects.models import (
    TrackableObject, TrackableObjectInstance,
    FollowUpEvent, FollowUpEventResponse,
    FollowUpEventTrackableObject, FollowUpEventDependency,
)


class AllActivitiesView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'trackable_objects/mobile/all_activities.html'

    def get_context_data(self, **kwargs):
        user = self.request.user
        user_group_ids = list(user.groups.values_list('id', flat=True))

        # All admin-unit IDs the user can access (assigned + descendants + ancestors)
        admin_unit_ids = set()
        for unit in user.administrative_units.all():
            self._collect_ancestor_ids(unit, admin_unit_ids)
            self._collect_descendant_ids(unit, admin_unit_ids)

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

        trackable_objects = list(
            TrackableObject.objects.filter(
                Exists(fe_linked_tos)
            ).distinct()
        )
        to_ids = [to.id for to in trackable_objects]

        # ── All instances the user can access ─────────────────────────
        instances = list(
            TrackableObjectInstance.objects.filter(
                Q(restrict_by_administrative_units=False) |
                Q(administrative_units__id__in=admin_unit_ids),
                trackable_object__in=to_ids,
            ).select_related('trackable_object').distinct()
        )

        # ── All active events user has group access to ────────────────
        matched_fe_groups_for_events = FollowUpEvent.groups.through.objects.filter(
            followupevent_id=OuterRef('pk'),
            group_id__in=user_group_ids,
        )

        events = list(
            FollowUpEvent.objects.filter(
                Exists(matched_fe_groups_for_events),
                is_active=True,
            )
        )
        event_ids = [e.id for e in events]

        # ── Build lookup maps (batch queries) ─────────────────────────
        # Which events are linked to which trackable objects
        event_to_map = defaultdict(set)  # event_id -> set of trackable_object_ids
        for link in FollowUpEventTrackableObject.objects.filter(
            follow_up_event_id__in=event_ids,
        ):
            event_to_map[link.follow_up_event_id].add(link.trackable_object_id)

        # Response lookup: (instance_id, event_id) -> response_id
        response_map = {}
        response_count_map = defaultdict(int)
        for resp in FollowUpEventResponse.objects.filter(
            trackable_object_instance__in=[i.id for i in instances],
            follow_up_event_id__in=event_ids,
        ).values('trackable_object_instance_id', 'follow_up_event_id', 'id'):
            key = (resp['trackable_object_instance_id'], resp['follow_up_event_id'])
            if key not in response_map:
                response_map[key] = resp['id']
            response_count_map[key] += 1

        # Standalone response lookup: event_id -> response_id (for global events)
        standalone_response_map = {}
        standalone_count_map = defaultdict(int)
        for resp in FollowUpEventResponse.objects.filter(
            created_by=user,
            trackable_object_instance__isnull=True,
            follow_up_event_id__in=event_ids,
        ).values('follow_up_event_id', 'id'):
            if resp['follow_up_event_id'] not in standalone_response_map:
                standalone_response_map[resp['follow_up_event_id']] = resp['id']
            standalone_count_map[resp['follow_up_event_id']] += 1

        # Dependency map: child_event_id -> set of parent_event_ids
        dep_map = defaultdict(set)
        for dep in FollowUpEventDependency.objects.filter(
            child_id__in=event_ids,
        ):
            dep_map[dep.child_id].add(dep.parent_id)

        # Admin unit names per instance (first admin unit for display)
        instance_unit_names = {}
        for inst in instances:
            au = inst.administrative_units.first()
            instance_unit_names[inst.id] = au.name if au else ''

        # ── Build flat activity list ──────────────────────────────────
        activities = []

        # Trackable-object lookup for quick access
        to_lookup = {to.id: to for to in trackable_objects}

        for instance in instances:
            to_id = instance.trackable_object_id
            # Get responded event IDs for dependency checking
            responded_event_ids = {
                eid for (iid, eid) in response_map if iid == instance.id
            }

            for event in events:
                linked_tos = event_to_map.get(event.id, set())
                is_global = len(linked_tos) == 0

                # Event must apply to this instance's trackable object (skip global/standalone)
                if to_id not in linked_tos:
                    continue

                # Check dependencies are fulfilled for this instance
                parent_ids = dep_map.get(event.id, set())
                if parent_ids and not parent_ids.issubset(responded_event_ids):
                    continue

                key = (instance.id, event.id)
                trackable_obj = to_lookup.get(to_id)

                activity = {
                    'event_name': event.name,
                    'event_id': event.id,
                    'event_order': event.order,
                    'instance_name': instance.identifier,
                    'instance_id': instance.id,
                    'object_name': trackable_obj.name if trackable_obj else '',
                    'object_icon': trackable_obj.icon if trackable_obj else 'fa-cube',
                    'object_color_tint': trackable_obj.color_tint if trackable_obj else '#eceff1',
                    'object_color_solid': trackable_obj.color_solid if trackable_obj else '#546e7a',
                    'admin_unit': instance_unit_names.get(instance.id, ''),
                    'is_global': is_global,
                    'is_one_off': event.is_one_off,
                    'is_pending': False,
                    'response_count': 0,
                    'type': 'instance',
                }

                if event.is_one_off:
                    activity['is_pending'] = key not in response_map
                    if key in response_map:
                        activity['response_id'] = response_map[key]
                        activity['url'] = reverse(
                            'trackableobjects:mobile:follow_up_event_response_update',
                            args=[event.id, response_map[key]],
                        )
                    else:
                        activity['url'] = reverse(
                            'trackableobjects:mobile:follow_up_event_response_create',
                            args=[instance.id, event.id],
                        )
                else:
                    activity['response_count'] = response_count_map.get(key, 0)
                    activity['url'] = reverse(
                        'trackableobjects:mobile:follow_up_event_detail',
                        args=[instance.id, event.id],
                    )

                activities.append(activity)

        # ── Standalone (global) events ────────────────────────────────
        for event in events:
            linked_tos = event_to_map.get(event.id, set())
            if linked_tos:
                continue  # Not a standalone event

            activity = {
                'event_name': event.name,
                'event_id': event.id,
                'event_order': event.order,
                'instance_name': '',
                'instance_id': None,
                'object_name': '',
                'object_icon': 'fa-globe-africa',
                'object_color_tint': '#f3e5f8',
                'object_color_solid': '#8e44ad',
                'admin_unit': '',
                'is_global': True,
                'is_one_off': event.is_one_off,
                'is_pending': False,
                'response_count': 0,
                'type': 'standalone',
            }

            if event.is_one_off:
                activity['is_pending'] = event.id not in standalone_response_map
                if event.id in standalone_response_map:
                    activity['response_id'] = standalone_response_map[event.id]
            else:
                activity['response_count'] = standalone_count_map.get(event.id, 0)

            activity['url'] = reverse(
                'trackableobjects:mobile:standalone_follow_up_event_list',
                args=[event.id],
            )

            activities.append(activity)

        # Sort by global event order
        activities.sort(key=lambda a: a.get('event_order', 0))

        # ── Counts for tabs ───────────────────────────────────────────
        kwargs['activities'] = activities
        kwargs['total_count'] = len(activities)
        kwargs['pending_count'] = sum(1 for a in activities if a['is_pending'])
        kwargs['global_count'] = sum(1 for a in activities if a['is_global'])

        # Object types for filter dropdown
        kwargs['trackable_objects'] = trackable_objects

        # Admin units for filter dropdown
        admin_units = set()
        for a in activities:
            if a['admin_unit']:
                admin_units.add(a['admin_unit'])
        kwargs['admin_units'] = sorted(admin_units)

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
            AllActivitiesView._collect_descendant_ids(child, id_set)
