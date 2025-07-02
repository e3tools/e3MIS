from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from django.http import Http404

from administrativelevels.models import AdministrativeUnit
from subprojects.api.serializers import SubprojectSerializer, SubprojectCustomFieldSerializer
from subprojects.models import SubprojectCustomField, Subproject, SubprojectFormResponse


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


class AdministrativeUnitListForSelectAPIView(AdministrativeUnitListAPIView):
    permission_classes = (AllowAny,)
    pagination_class = None


class LastSubprojectCustomFieldRetrieveAPIView(generics.RetrieveAPIView):
    queryset = SubprojectCustomField.objects.all()
    permission_classes = (IsAuthenticated,)
    serializer_class = SubprojectCustomFieldSerializer

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        try:
            obj = queryset.latest('created_at')
        except SubprojectCustomField.DoesNotExist:
            raise Http404

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj


class SubprojectCustomFieldRetrieveAPIView(generics.ListAPIView):
    pagination_class = None
    queryset = SubprojectCustomField.objects.all()
    serializer_class = SubprojectCustomFieldSerializer

    def list(self, request, *args, **kwargs):
        resp_list = list()
        administrative_unit_id = self.request.query_params.get('administrative-unit', None)

        administrative_unit = AdministrativeUnit.objects.get(pk=administrative_unit_id)
        all_lower_children = self.get_lower_children(administrative_unit)
        for child in all_lower_children:
            subprojects = Subproject.objects.filter(administrative_level=child)
            resp_list += list(SubprojectCustomField.objects.filter(subprojects__in=subprojects).values(
                'name', 'id', 'subprojects__name', 'subprojects__id', 'subprojects__administrative_level__name'))

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


