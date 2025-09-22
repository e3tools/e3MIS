from datetime import timedelta
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from django.utils import timezone
from rest_framework.views import APIView

from .models import ApiToken
from .serializers import TokenCreateSerializer, TokenOutSerializer


class TokenViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"])
    def create_token(self, request):
        ser = TokenCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ttl = None
        if "ttl_hours" in ser.validated_data:
            ttl = timedelta(hours=ser.validated_data["ttl_hours"])

        raw_token, obj = ApiToken.mint(
            user=request.user,
            name=ser.validated_data.get("name", ""),
            scopes=ser.validated_data.get("scopes", []),
            ttl=ttl,
        )
        out = TokenOutSerializer({
            "token": raw_token,
            "id": obj.public_id,
            "name": obj.name,
            "scopes": obj.scopes,
            "expires_at": obj.expires_at,
        })
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def list_tokens(self, request):
        tokens = ApiToken.objects.filter(user=request.user).order_by("-created_at")
        data = [
            {
                "id": t.public_id,
                "name": t.name,
                "scopes": t.scopes,
                "last_used_at": t.last_used_at,
                "expires_at": t.expires_at,
                "revoked": bool(t.revoked_at),
            }
            for t in tokens
        ]
        return Response(data)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        try:
            t = ApiToken.objects.get(user=request.user, public_id=pk, revoked_at__isnull=True)
        except ApiToken.DoesNotExist:
            return Response({"detail": "Not found or already revoked."}, status=404)
        t.revoked_at = timezone.now()
        t.save(update_fields=["revoked_at"])
        return Response(status=204)


class TestAPIView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response({"detail": "Good to go"}, status=200)
