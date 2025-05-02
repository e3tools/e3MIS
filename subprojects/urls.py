from django.urls import path

from subprojects.infrastructure.views.subproject_create_view import SubprojectCreateView
from subprojects.infrastructure.views.subproject_list_view import SubprojectListView
from subprojects.infrastructure.views.subproject_update_view import SubprojectUpdateView

app_name = 'subprojects'

urlpatterns = [
    path('', SubprojectListView.as_view(), name='subproject_list'),
    path('create', SubprojectCreateView.as_view(), name='subproject_create'),
    path('subproject/<int:pk>/update/', SubprojectUpdateView.as_view(), name='subproject_update'),

]

