from rest_framework import routers

from trackableobjects.api.routers import router as trackable_object_router
from authorization.api.routers import router as authorization_router

from .views import TokenViewSet

router = routers.SimpleRouter()

token_create = TokenViewSet.as_view({"post": "create_token"})
token_list = TokenViewSet.as_view({"get": "list_tokens"})
token_revoke = TokenViewSet.as_view({"post": "revoke"})

urlpatterns = [
    # path("tokens/", token_list, name="token-list"),
    # path("tokens/create/", token_create, name="token-create"),
    # path("tokens/<str:pk>/revoke/", token_revoke, name="token-revoke"),
] + trackable_object_router.urls + authorization_router.urls
