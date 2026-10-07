from django.db import connection
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(
    responses=inline_serializer(
        "Health",
        {
            "status": serializers.CharField(),
            "server_time": serializers.DateTimeField(),
            "clock_anchor": serializers.CharField(),
        },
    )
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Liveness/readiness probe; also lets the app check connectivity and server time."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    from .trusted_clock import issue_anchor

    # clock_anchor: a signed server time the app measures offline time from (trusted clock).
    return Response({"status": "ok", "server_time": timezone.now().isoformat(), "clock_anchor": issue_anchor()})


@extend_schema(exclude=True)
@api_view(["GET", "POST"])
@authentication_classes([])  # the cron secret is not a user JWT
@permission_classes([AllowAny])
def run_jobs(request):
    """Scheduled-job trigger for platforms without a long-running scheduler (Vercel Cron).

    Each job decides in programme time whether it is due, so calling this more often
    than necessary is harmless.
    """
    import hmac

    from django.conf import settings

    from .jobs import run_due_jobs

    expected = f"Bearer {settings.CRON_SECRET}" if settings.CRON_SECRET else None
    given = request.headers.get("Authorization", "")
    if not expected or not hmac.compare_digest(given, expected):
        return Response(status=401)
    result = run_due_jobs()
    return Response({k: (v if isinstance(v, int) or v is None else "generated") for k, v in result.items()})
