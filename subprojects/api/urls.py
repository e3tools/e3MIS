from django.urls import path
from subprojects.api import views


urlpatterns = [
    path('administrative-unit/<int:pk>', views.AdministrativeUnitListAPIView.as_view()),
    path('latest-custom-field', views.LastSubprojectCustomFieldRetrieveAPIView.as_view()),
]
