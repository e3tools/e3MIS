from rest_framework import generics
from rest_framework.response import Response

from django.db.models import Subquery
from django.template.defaultfilters import date

from administrativelevels.models import AdministrativeUnit
from trackableobjects.api.serializers import TrackableObjectInstanceSerializer
from trackableobjects.models import TrackableObjectInstance, FollowUpEventResponse, FollowUpEvent


class TrackableObjectInstanceRetrieveAPIView(generics.ListAPIView):
    pagination_class = None
    queryset = TrackableObjectInstance.objects.all()
    serializer_class = TrackableObjectInstanceSerializer

    def list(self, request, *args, **kwargs):
        resp_list = list()
        administrative_unit_id = self.request.query_params.get('administrative-unit', None)
        trackable_object = self.request.query_params.get('trackable-object', None)

        administrative_unit = AdministrativeUnit.objects.get(pk=administrative_unit_id)
        all_lower_children = self.get_lower_children(administrative_unit)
        for child in all_lower_children:
            node_list = list(TrackableObjectInstance.objects.filter(
                administrative_units=child,
                trackable_object__id=trackable_object,
            ).values(
                'created_at', 'id', 'trackable_object__id'))
            for node in node_list:
                node['created_at'] = date(node['created_at'], "N j, y")
                sub_qs = Subquery(FollowUpEvent.objects.filter(
                    trackable_object__id=node['trackable_object__id'],
                    is_one_off=True
                ).values('id'))
                if FollowUpEventResponse.objects.filter(trackable_object_instance__id=node['id'],
                                                        follow_up_event__id__in=sub_qs).exists():
                    node['has_badge'] = False
                else:
                    node['has_badge'] = True
            resp_list += node_list

        return Response(resp_list)

    def get_lower_children(self, administrative_unit):
        administrative_units = list()

        def get_children(node):
            if node.children.all():
                for children in node.children.all():
                    get_children(children)
            else:
                administrative_units.append(node)

        get_children(administrative_unit)

        return administrative_units
