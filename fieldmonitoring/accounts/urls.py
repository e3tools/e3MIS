from django.urls import path
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from .serializers import EmailOrUsernameTokenSerializer
from .views import MeView

urlpatterns = [
    path(
        "token/",
        TokenObtainPairView.as_view(serializer_class=EmailOrUsernameTokenSerializer),
        name="fm_token_obtain_pair",
    ),
    path("token/refresh/", TokenRefreshView.as_view(), name="fm_token_refresh"),
    path("logout/", TokenBlacklistView.as_view(), name="fm_token_blacklist"),
    path("me/", MeView.as_view(), name="fm_me"),
]
