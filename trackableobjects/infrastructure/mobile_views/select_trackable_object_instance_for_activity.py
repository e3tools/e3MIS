import json

from django.views.generic.detail import DetailView
from django.db.models import Count, OuterRef, Exists

from administrativelevels.models import AdministrativeUnit
from trackableobjects.models import (
    TrackableObject, TrackableObjectInstance,
    FollowUpEvent, FollowUpEventTrackableObject,
)

from src.permissions import IsFieldAgentUserMixin


class MobileViewsTrackableObjectInstanceActivityListView(IsFieldAgentUserMixin, DetailView):
    template_name = 'trackable_objects/mobile/select_trackable_object_instance_for_activity.html'
    queryset = TrackableObject.objects.all()

    def get_queryset(self):
        user_group_ids = list(self.request.user.groups.values_list('id', flat=True))

        # FollowUpEvents accessible to this user (at least one shared group)
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

        return TrackableObject.objects.filter(
            Exists(fe_linked_tos)
        ).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['trackable_object'] = self.kwargs.get('pk', None)

        user_units = list(
            self.request.user.administrative_units.all()
            .select_related('level')
        )

        if not user_units:
            context['units_json'] = '[]'
            return context

        # Build full accessible tree (ancestors + assigned units + descendants)
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
                # Need to ensure level is loaded
                if not hasattr(current, '_level_cache'):
                    current = AdministrativeUnit.objects.select_related('level').get(pk=current.pk)
                all_units[current.id] = current
                current = current.parent

        for unit in user_units:
            collect_descendants(unit)
            collect_ancestors(unit)

        # Instance counts per admin unit (direct assignment)
        direct_counts = dict(
            TrackableObjectInstance.objects.filter(
                trackable_object=self.object,
                administrative_units__id__in=all_units.keys(),
            ).values_list('administrative_units__id').annotate(
                count=Count('id', distinct=True)
            )
        )

        # Compute subtree instance counts (unit + all descendants)
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

        # Build JSON, filtering out units with 0 instances in subtree
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

        context['units_json'] = json.dumps(units_data)
        return context
