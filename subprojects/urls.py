from django.urls import path, include

from subprojects.infrastructure.views.contractor_list import ContractorListView
from subprojects.infrastructure.views.subproject_create_view import SubprojectCreateView
from subprojects.infrastructure.views.subproject_list_view import SubprojectListView
from subprojects.infrastructure.views.subproject_update_view import SubprojectUpdateView
from subprojects.infrastructure.views.record_subproject_progress import SubprojectProgressCreateView
from subprojects.infrastructure.views.subproject_custom_form_create_view import SubprojectCustomFieldsCreateView
from subprojects.infrastructure.views.dashboard_view import DashboardView
from subprojects.infrastructure.views.subproject_custom_form_list import SubprojectCustomFieldListView
from subprojects.infrastructure.views.subprojects_by_administrativeunit import AdministrativeUnitSubprojectsView
from subprojects.infrastructure.mobile_views.index import IndexTemplateView
from subprojects.infrastructure.mobile_views.register_menu import RegisterMenuTemplateView
from subprojects.infrastructure.mobile_views.select_subproject_for_activity import SelectSubprojectForActivityView
from subprojects.infrastructure.mobile_views.select_subproject_custom_field import SelectSubprojectCustomFieldView
from subprojects.infrastructure.mobile_views.custom_form_create_view import CustomFormUpdateView
from subprojects.infrastructure.mobile_views.register_subproject import RegisterSubprojectView


app_name = 'subprojects'
urlpatterns = [
    path('', SubprojectListView.as_view(), name='subproject_list'),
    path('api/', include('subprojects.api.urls')),
    path('dashboard/', DashboardView.as_view(), name='subproject_dashboard'),
    path('create', SubprojectCreateView.as_view(), name='subproject_create'),
    path('<int:pk>/update/', SubprojectUpdateView.as_view(), name='subproject_update'),
    path('<int:pk>/progress/', SubprojectProgressCreateView.as_view(), name='subproject_progress'),
    path('custom-fields/create/', SubprojectCustomFieldsCreateView.as_view(), name='subproject_custom_fields_create'),
    path('custom-fields/', SubprojectCustomFieldListView.as_view(), name='subproject_custom_fields'),
    path('subprojects-adminunit/', AdministrativeUnitSubprojectsView.as_view(), name='subproject_adminunit'),
    path('contractors/', ContractorListView.as_view(), name='contractor_list'),
    path('mobile/', include(([
        path('', IndexTemplateView.as_view(), name='index'),
        path('register/', RegisterMenuTemplateView.as_view(), name='register-menu'),
        path('register/sub-project/', RegisterSubprojectView.as_view(), name='register-subproject'),
        path('submit-activity/', SelectSubprojectForActivityView.as_view(), name='select-subproject-for-activity'),
        path('select-custom-fields/<int:subproject>/', SelectSubprojectCustomFieldView.as_view(), name='select-subproject-custom-fields'),
        path('custom-form-update/<int:pk>/subproject/<int:subproject>/', CustomFormUpdateView.as_view(), name='custom-form-update'),
    ], 'mobile'))),
]

