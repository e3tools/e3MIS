from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from authorization.infrastructure.forms.email_authentication_form import EmailAuthenticationForm

app_name = 'authorization'
urlpatterns = [
    path('', auth_views.LoginView.as_view(
        authentication_form=EmailAuthenticationForm,
        template_name='auth/login.html',
        redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
