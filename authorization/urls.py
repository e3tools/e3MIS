from django.contrib.auth import views as auth_views
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from authorization.infrastructure.forms.email_authentication_form import EmailAuthenticationForm
from authorization.infrastructure.views.field_agent_list import FieldAngentListView

app_name = 'authorization'
urlpatterns = [
    path('', auth_views.LoginView.as_view(
        authentication_form=EmailAuthenticationForm,
        template_name='auth/login.html',
        redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('field-agents/', FieldAngentListView.as_view(), name='field_angent_list'),
    path('api/', include([
        path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
        path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    ])),
]
