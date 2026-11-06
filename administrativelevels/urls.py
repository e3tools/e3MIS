from django.urls import path, include
from .api import urls as api_urls

from administrativelevels.infrastructure.views.administrative_levels_list_view import AdministrativeLevelsListView
from administrativelevels.infrastructure.views.administrative_unit_list_parent import AdministrativeUnitListParentView
from administrativelevels.infrastructure.views.administrative_unit_detail_view import AdministrativeUnitDetailView
from administrativelevels.infrastructure.views.unit_import import AdministrativeUnitImportView
from administrativelevels.infrastructure.views.unit_import_confirm import AdministrativeUnitImportConfirmView
from administrativelevels.infrastructure.views.unit_import_template import AdministrativeUnitImportTemplateView

app_name = 'administrativelevels'

urlpatterns = [
    path('', AdministrativeLevelsListView.as_view(), name='administrative_levels_list'),
    path('management', AdministrativeLevelsListView.as_view(), name='administrative_levels_list'),
    path('units', AdministrativeUnitDetailView.as_view(), name='administrative_unit_root'),
    path('unit/<int:pk>', AdministrativeUnitDetailView.as_view(), name='administrative_unit_detail'),
    path('units/import/', AdministrativeUnitImportView.as_view(), name='administrative_unit_import'),
    path('units/import/confirm/', AdministrativeUnitImportConfirmView.as_view(),
         name='administrative_unit_import_confirm'),
    path('units/import/template/', AdministrativeUnitImportTemplateView.as_view(),
         name='administrative_unit_import_template'),
    path('get-children/<int:parent>', AdministrativeUnitListParentView.as_view(), name='administrative_levels_list_parent'),
    path('api/', include(api_urls)),

]

