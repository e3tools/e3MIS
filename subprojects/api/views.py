from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from administrativelevels.models import AdministrativeUnit
from subprojects.api.serializers import SubprojectSerializer
from subprojects.models import Subproject


class AdministrativeUnitListAPIView(generics.ListAPIView):
    queryset = AdministrativeUnit.objects.all()
    permission_classes = (IsAuthenticated,)
    serializer_class = SubprojectSerializer

    def get_queryset(self):
        queryset = self.queryset

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        assert lookup_url_kwarg in self.kwargs, (
            'Expected view %s to be called with a URL keyword argument '
            'named "%s". Fix your URL conf, or set the `.lookup_field` '
            'attribute on the view correctly.' %
            (self.__class__.__name__, lookup_url_kwarg)
        )

        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        administrative_unit = generics.get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, administrative_unit)
        administrative_unit_ids = self.get_administrative_unit_children(administrative_unit)

        return Subproject.objects.filter(administrative_level__id__in=administrative_unit_ids)

    def get_administrative_unit_children(self, administrative_unit):
        children = administrative_unit.children.all()
        children_ids = list()
        for child in children:
            children_ids += self.get_administrative_unit_children(child)
        children_ids.append(administrative_unit.id)
        return children_ids

