from django.urls import path
from subprojects.api import views

app_name = 'api'
urlpatterns = [
    path('administrative-unit-select/<int:pk>', views.AdministrativeUnitListForSelectAPIView.as_view(), name='administrative-unit-select'),
    path('administrative-unit/<int:pk>', views.AdministrativeUnitListAPIView.as_view()),
    path('latest-custom-field', views.LastSubprojectCustomFieldRetrieveAPIView.as_view()),
]
