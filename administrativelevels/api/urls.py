from django.urls import path
from administrativelevels.api import views

app_name = 'api'
urlpatterns = [
    path('administrative-unit/<int:pk>', views.AdministrativeLevelChildrenAPIView.as_view(), name='administrative-level-children'),
    path('administrative-unit-root/', views.AdministrativeUnitRootAPIView.as_view(), name='administrative-unit-root'),
    path('administrative-unit/<int:pk>/ancestors/', views.AdministrativeUnitAncestorChainAPIView.as_view(), name='administrative-unit-ancestors'),
    path('administrative-unit/<int:pk>/descendants/', views.AdministrativeUnitDescendantsAPIView.as_view(), name='administrative-unit-descendants'),
]
