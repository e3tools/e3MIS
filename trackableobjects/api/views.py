from rest_framework import generics
from rest_framework.response import Response

from django.db.models import Subquery
from django.template.defaultfilters import date

from authorization.models import CustomUser
from administrativelevels.models import AdministrativeUnit
from trackableobjects.api.serializers import TrackableObjectInstanceSerializer
from trackableobjects.models import TrackableObjectInstance, FollowUpEventResponse, FollowUpEvent


class TrackableObjectInstanceRetrieveAPIView(generics.ListAPIView):
    pagination_class = None
    queryset = TrackableObjectInstance.objects.all()
    serializer_class = TrackableObjectInstanceSerializer

    def list(self, request, *args, **kwargs):
        resp_list = list()
        ids_in = list()
        administrative_unit_id = self.request.query_params.get('administrative-unit', None)
        trackable_object = self.request.query_params.get('trackable-object', None)

        if administrative_unit_id == '':
            user = CustomUser.objects.filter(id=self.request.META.get('HTTP_USER', None)).first()
            if user:
                administrative_unit = user.administrative_unit
            else:
                administrative_unit = AdministrativeUnit.objects.none()
        else:
            administrative_unit = AdministrativeUnit.objects.get(pk=administrative_unit_id)

        all_lower_children = self.get_lower_children(administrative_unit)
        for child in all_lower_children:
            trackable_object_instance_qs = TrackableObjectInstance.objects.filter(
                administrative_units=child,
                trackable_object__id=trackable_object,
            ).distinct()
            for obj in trackable_object_instance_qs:
                if obj.id not in ids_in:
                    node = {
                        'created_at': date(obj.created_at, "N j, y"),
                        'id': obj.id,
                        'trackable_object__id': obj.trackable_object.id,
                        'identifier': obj.identifier,
                    }

                    sub_qs_1 = FollowUpEvent.objects.filter(
                        trackable_object__id=node['trackable_object__id'],
                        is_one_off=True
                    )
                    sub_qs_2 = FollowUpEventResponse.objects.filter(
                            trackable_object_instance__id=node['id'],
                            follow_up_event__id__in=Subquery(sub_qs_1.values('id'))
                    )

                    if sub_qs_1.count() != sub_qs_2.count():
                        node['has_badge'] = True
                    else:
                        node['has_badge'] = False

                    ids_in.append(obj.id)
                    resp_list.append(node)

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
