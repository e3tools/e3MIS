from django.urls import path

from administrativelevels.infrastructure.views.administrative_levels_list_view import AdministrativeLevelsListView

app_name = 'administrativelevels'

urlpatterns = [
    path('', AdministrativeLevelsListView.as_view(), name='administrative_levels_list'),

]

