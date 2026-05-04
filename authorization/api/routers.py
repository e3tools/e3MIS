from rest_framework import routers

from authorization.api import views

router = routers.SimpleRouter()

router.register(r'user', views.UserViewSet)
