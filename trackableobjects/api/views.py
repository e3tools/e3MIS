from rest_framework import generics, permissions
from rest_framework.authentication import SessionAuthentication
from rest_framework.views import APIView
from rest_framework.response import Response

from django.db.models import Subquery
from django.template.defaultfilters import date

from authorization.models import CustomUser
from administrativelevels.models import AdministrativeUnit
from trackableobjects.api.serializers import TrackableObjectInstanceSerializer
from trackableobjects.models import (
    TrackableObjectInstance, FollowUpEventResponse, FollowUpEvent, FollowUpEventTrackableObject
)


class TrackableObjectInstanceRetrieveAPIView(generics.ListAPIView):
    pagination_class = None
    queryset = TrackableObjectInstance.objects.all()
    serializer_class = TrackableObjectInstanceSerializer

    def list(self, request, *args, **kwargs):
        resp_list = list()
        ids_in = list()
        administrative_unit_id = self.request.query_params.get('administrative-unit', None)
        trackable_object = self.request.query_params.get('trackable-object', None)

        # Collect all accessible admin unit IDs (ancestors + descendants)
        if administrative_unit_id == '':
            user = CustomUser.objects.filter(id=self.request.META.get('HTTP_USER', None)).first()
            if user:
                all_unit_ids = set()
                for unit in user.administrative_units.all():
                    self._collect_ancestor_ids(unit, all_unit_ids)
                    self._collect_descendant_ids(unit, all_unit_ids)
            else:
                all_unit_ids = set()
        else:
            administrative_unit = AdministrativeUnit.objects.get(pk=administrative_unit_id)
            all_unit_ids = set()
            self._collect_ancestor_ids(administrative_unit, all_unit_ids)
            self._collect_descendant_ids(administrative_unit, all_unit_ids)

        from django.db.models import Q
        trackable_object_instance_qs = TrackableObjectInstance.objects.filter(
            Q(restrict_by_administrative_units=False) |
            Q(administrative_units__id__in=all_unit_ids),
            trackable_object__id=trackable_object,
        ).select_related('trackable_object').distinct()

        for obj in trackable_object_instance_qs:
            if obj.id not in ids_in:
                node = {
                    'created_at': date(obj.created_at, "N j, y"),
                    'created_at_iso': obj.created_at.isoformat(),
                    'id': obj.id,
                    'trackable_object__id': obj.trackable_object.id,
                    'identifier': obj.identifier,
                }

                sub_qs_1 = FollowUpEvent.objects.filter(
                    trackable_objects__id=node['trackable_object__id'],
                    is_one_off=True
                )
                sub_qs_2 = FollowUpEventResponse.objects.filter(
                        trackable_object_instance__id=node['id'],
                        follow_up_event__id__in=Subquery(sub_qs_1.values('id'))
                )

                pending_count = sub_qs_1.count() - sub_qs_2.count()
                node['pending_count'] = max(pending_count, 0)
                node['has_badge'] = pending_count > 0

                ids_in.append(obj.id)
                resp_list.append(node)

        return Response(resp_list)

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
            TrackableObjectInstanceRetrieveAPIView._collect_descendant_ids(child, id_set)


class FollowUpEventReorderAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        trackable_object_id = request.data.get('trackable_object_id')
        ordered_ids = request.data.get('ordered_ids', [])

        for index, event_id in enumerate(ordered_ids):
            FollowUpEventTrackableObject.objects.filter(
                trackable_object_id=trackable_object_id,
                follow_up_event_id=event_id,
            ).update(order=index + 1)

        return Response({'status': 'ok'})
