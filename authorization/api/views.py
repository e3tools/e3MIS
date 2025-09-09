from rest_framework import viewsets
from django.contrib.auth import get_user_model

from api.permissions import ReadOnly
from authorization.api.serializers import UserSerializer

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOnly]
    queryset = User.objects.all()
    serializer_class = UserSerializer
