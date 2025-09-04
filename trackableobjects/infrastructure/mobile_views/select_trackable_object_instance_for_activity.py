from django.views.generic.detail import DetailView
from django.db.models import Q, F, Count, Sum

from administrativelevels.models import AdministrativeUnit
from trackableobjects.models import TrackableObject, TrackableObjectInstance

from src.permissions import IsFieldAgentUserMixin


class MobileViewsTrackableObjectInstanceActivityListView(IsFieldAgentUserMixin, DetailView):
    template_name = 'trackable_objects/mobile/select_trackable_object_instance_for_activity.html'
    queryset = TrackableObject.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['trackable_object'] = self.kwargs.get('pk', None)
        administrative_units_qs = AdministrativeUnit.objects.filter(
            id__in=self.get_descendants(self.request.user.administrative_unit)
        ).select_related('parent')

        response_list = list()
        for administrative_unit in administrative_units_qs:

            base_instances = TrackableObjectInstance.objects.filter(
                administrative_units=administrative_unit,
                trackable_object=self.object
            )

            qs = base_instances.annotate(
                total_one_off_events=Count(
                    'trackable_object__follow_up_events',
                    filter=Q(trackable_object__follow_up_events__is_one_off=True),
                    distinct=True
                ),
                total_one_off_responses=Count(
                    'follow_up_responses',
                    filter=Q(follow_up_responses__follow_up_event__is_one_off=True),
                    distinct=True
                ),
            ).annotate(pending_one_off=F('total_one_off_events') - F('total_one_off_responses'))

            result = qs.aggregate(pending_total=Sum('pending_one_off'))['pending_total'] or ''

            child = {
                'id': administrative_unit.id,
                'name': administrative_unit.name,
                'pending_responses': result,
                'trackable_instances_count': base_instances.count() or ''
            }

            flag = False
            for node in response_list:
                if 'parent_id' in node and node['parent_id'] == administrative_unit.parent.id:
                    flag = True
                    node['children'].append(child)
            if not flag:
                response_list.append({
                    'parent_id': administrative_unit.parent.id,
                    'name': administrative_unit.parent.name,
                    'children': [child]
                })

        context['administrative_units'] = response_list
        return context

    def get_descendants(self, administrative_unit):
        descendants = list()

        def recurse(node):
            if node.children.exists():
                for child in node.children.all():
                    recurse(child)
            else:
                descendants.append(node.id)

        recurse(administrative_unit)
        return descendants
