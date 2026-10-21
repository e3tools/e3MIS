from rest_framework import viewsets
from django.contrib.auth import get_user_model

from api.permissions import IsNotFieldAgent, ReadOnly
from rest_framework.permissions import IsAuthenticated
from authorization.api.serializers import UserSerializer

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOnly, IsAuthenticated, IsNotFieldAgent]
    queryset = User.objects.all()
    serializer_class = UserSerializer
