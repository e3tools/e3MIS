from django.urls import path

from subprojects.infrastructure.views.subproject_create_view import SubprojectCreateView
from subprojects.infrastructure.views.subproject_list_view import SubprojectListView
from subprojects.infrastructure.views.subproject_update_view import SubprojectUpdateView
from subprojects.infrastructure.views.record_subproject_progress import SubprojectProgressCreateView
from subprojects.infrastructure.views.dashboard_view import DashboardView

app_name = 'subprojects'

urlpatterns = [
    path('', SubprojectListView.as_view(), name='subproject_list'),
    path('dashboard/', DashboardView.as_view(), name='subproject_dashboard'),
    path('create', SubprojectCreateView.as_view(), name='subproject_create'),
    path('subproject/<int:pk>/update/', SubprojectUpdateView.as_view(), name='subproject_update'),
    path('subproject/<int:pk>/progress/', SubprojectProgressCreateView.as_view(), name='subproject_progress'),
]

