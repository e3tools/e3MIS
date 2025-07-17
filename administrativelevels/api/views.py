from rest_framework import generics, permissions
from django.db.models.query import QuerySet

from administrativelevels.models import AdministrativeUnit
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
