from django.urls import path

from subprojects.infrastructure.views.subproject_create_view import SubprojectCreateView
from subprojects.infrastructure.views.subproject_list_view import SubprojectListView
from subprojects.infrastructure.views.subproject_update_view import SubprojectUpdateView
from subprojects.infrastructure.views.record_subproject_progress import SubprojectProgressCreateView
from subprojects.infrastructure.views.subproject_custom_form_create_view import SubprojectCustomFieldsCreateView

app_name = 'subprojects'

urlpatterns = [
    path('', SubprojectListView.as_view(), name='subproject_list'),
    path('create', SubprojectCreateView.as_view(), name='subproject_create'),
    path('<int:pk>/update/', SubprojectUpdateView.as_view(), name='subproject_update'),
    path('<int:pk>/progress/', SubprojectProgressCreateView.as_view(), name='subproject_progress'),
    path('custom-fields/', SubprojectCustomFieldsCreateView.as_view(), name='subproject_custom_fields'),
]

