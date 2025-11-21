from rest_framework import routers
from django.urls import path, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from trackableobjects.api.routers import router as trackable_object_router
from authorization.api.routers import router as authorization_router

from .views import TokenViewSet

router = routers.SimpleRouter()

token_create = TokenViewSet.as_view({"post": "create_token"})
token_list = TokenViewSet.as_view({"get": "list_tokens"})
token_revoke = TokenViewSet.as_view({"post": "revoke"})

schema_view = get_schema_view(
   openapi.Info(
      title="Snippets API",
      default_version='v1',
      description="Test description",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@snippets.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=[permissions.AllowAny,],
)

urlpatterns = [
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
] + trackable_object_router.urls + authorization_router.urls
