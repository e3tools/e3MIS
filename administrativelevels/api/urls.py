from django.urls import path
from administrativelevels.api import views

app_name = 'api'
urlpatterns = [
    path('administrative-unit/<int:pk>', views.AdministrativeLevelChildrenAPIView.as_view(), name='administrative-level-children'),
]
