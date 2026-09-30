from rest_framework import generics

from .serializers import UserSerializer


class MeView(generics.RetrieveUpdateAPIView):
    """The authenticated user's own profile."""

    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
