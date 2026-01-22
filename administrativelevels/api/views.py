from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models.query import QuerySet

from administrativelevels.models import AdministrativeUnit, AdministrativeLevel
from .serializers import AdministrativeUnitModelSerializer


class AdministrativeLevelChildrenAPIView(generics.ListAPIView):
    permission_classes = (permissions.AllowAny,)
    pagination_class = None
    queryset = AdministrativeUnit.objects.all()
    serializer_class = AdministrativeUnitModelSerializer

    def get_queryset(self):
        queryset = self.queryset
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        if isinstance(queryset, QuerySet):
            # Ensure queryset is re-evaluated on each request.
            queryset = queryset.filter(parent__id=self.kwargs[lookup_url_kwarg])
        return queryset


class AdministrativeUnitRootAPIView(generics.ListAPIView):
    """Returns all root-level administrative units (those without a parent)"""
    permission_classes = (permissions.AllowAny,)
    pagination_class = None
    queryset = AdministrativeUnit.objects.filter(parent__isnull=True)
    serializer_class = AdministrativeUnitModelSerializer


class AdministrativeUnitAncestorChainAPIView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, pk):
        try:
            unit = AdministrativeUnit.objects.get(pk=pk)
        except AdministrativeUnit.DoesNotExist:
            return Response({'error': 'Administrative unit not found'}, status=404)

        chain = []
        current = unit
        while current is not None:
            chain.append({
                'id': current.id,
                'name': current.name,
                'level_id': current.level_id,
                'level_name': current.level.name,
                'level_order': current.level.order,
                'parent_id': current.parent_id,
            })
            current = current.parent

        chain.reverse()
        levels = list(AdministrativeLevel.objects.values('id', 'name', 'order').order_by('order'))

        return Response({
            'chain': chain,
            'levels': levels
        })
