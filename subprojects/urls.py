from django.urls import path

from subprojects.infrastructure.views.subproject_create_view import SubprojectCreateView
from subprojects.infrastructure.views.subproject_list_view import SubprojectListView

app_name = 'subprojects'

urlpatterns = [
    path('', SubprojectListView.as_view(), name='subproject_list'),
    path('create', SubprojectCreateView.as_view(), name='subproject_create'),

]

