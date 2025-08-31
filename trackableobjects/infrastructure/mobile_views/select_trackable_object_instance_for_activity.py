from django.views.generic.detail import DetailView
from django.db.models import Exists, OuterRef

from administrativelevels.models import AdministrativeUnit
from trackableobjects.models import TrackableObject, TrackableObjectInstance, FollowUpEventResponse, FollowUpEvent

from src.permissions import IsFieldAgentUserMixin


class MobileViewsTrackableObjectInstanceActivityListView(IsFieldAgentUserMixin, DetailView):
    template_name = 'trackable_objects/mobile/select_trackable_object_instance_for_activity.html'
    queryset = TrackableObject.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        administrative_units_qs = AdministrativeUnit.objects.filter(
            id__in=self.get_descendants(self.request.user.administrative_unit)).select_related('parent')

        response_list = list()
        for administrative_unit in administrative_units_qs:
            flag = False
            for node in response_list:
                if 'parent_id' in node and node['parent_id'] == administrative_unit.parent.id:

                    base_instances = TrackableObjectInstance.objects.filter(
                        administrative_units=administrative_unit
                    )

                    # Does this instance's TrackableObject define at least one one-off event?
                    one_off_event_exists = FollowUpEvent.objects.filter(
                        trackable_object=OuterRef('trackable_object'),
                        is_one_off=True,
                    )

                    # Does this instance already have any response for any one-off event?
                    one_off_response_exists = FollowUpEventResponse.objects.filter(
                        trackable_object_instance=OuterRef('pk'),
                        follow_up_event__is_one_off=True,
                    )

                    qs = (
                        base_instances
                        .annotate(has_one_off=Exists(one_off_event_exists),
                                  has_one_off_response=Exists(one_off_response_exists))
                        .filter(has_one_off=True, has_one_off_response=False)
                        .distinct()
                    )

                    node['children'].append({
                        'id': administrative_unit.id,
                        'name': administrative_unit.name,
                        'pending_responses': qs.count() or ''
                    })
                    flag = True
            if not flag:
                response_list.append({
                    'parent_id': administrative_unit.parent.id,
                    'name': administrative_unit.parent.name,
                    'children': [{'id': administrative_unit.id, 'name': administrative_unit.name}]
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
