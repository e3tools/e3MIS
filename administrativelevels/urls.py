from django.urls import path

from administrativelevels.infrastructure.views.administrative_levels_list_view import AdministrativeLevelsListView
from administrativelevels.infrastructure.views.administrative_unit_list_parent import AdministrativeUnitListParentView

app_name = 'administrativelevels'

urlpatterns = [
    path('', AdministrativeLevelsListView.as_view(), name='administrative_levels_list'),
    path('get-children/<int:parent>', AdministrativeUnitListParentView.as_view(), name='administrative_levels_list_parent'),

]

