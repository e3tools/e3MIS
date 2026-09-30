import csv
import io
from datetime import date

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from authorization.models import Role, User
from fieldmonitoring.compliance.services import current_pause
from fieldmonitoring.accounts.permissions import IsRdpOrAdmin, IsSupervisorOrAbove
from fieldmonitoring.core.negotiation import IgnoreFormatParamNegotiation
from fieldmonitoring.core import clock

from . import services
from .models import Warning, WarningEntry


class EntrySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name")
    user_id = serializers.CharField(source="user.id")
    supervisor = serializers.CharField(source="supervisor.full_name", default=None)
    supervisor_id = serializers.CharField(source="supervisor.id", default=None)

    class Meta:
        model = WarningEntry
        fields = (
            "rank", "kind", "user_id", "full_name", "role", "threshold_days", "area",
            "days_since_last_verified", "delta_days", "supervisor", "supervisor_id", "detail",
        )


class WarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warning
        fields = (
            "week_of", "period_start", "period_end", "generated_at", "paused_count",
            "total_field_staff", "overdue_high_risk_reviews", "thresholds",
        )


def _payload(warning, viewer):
    entries = list(services.entries_for(warning, viewer))
    previous = Warning.objects.filter(week_of__lt=warning.week_of).order_by("-week_of").first()
    prev_regularity = (
        services.entries_for(previous, viewer).filter(kind="regularity").count() if previous else None
    )
    data = WarningSerializer(warning).data
    if viewer.role == Role.SC:
        # The SC's view is their team: totals are scoped the same way as the entries.
        team = User.objects.filter(supervisor=viewer, is_active=True)
        data["total_field_staff"] = team.count()
        data["paused_count"] = sum(1 for u in team if current_pause(u, warning.week_of))
    return {
        **data,
        "filtered_to_team": viewer.role == Role.SC,
        "summary": {
            "over_threshold": sum(1 for e in entries if e.kind == "regularity"),
            "quota_at_risk": sum(1 for e in entries if e.kind == "quota"),
            "rotation": sum(1 for e in entries if e.kind == "rotation"),
            "previous_over_threshold": prev_regularity,
        },
        "entries": EntrySerializer(entries, many=True).data,
    }


class WarningListView(APIView):
    permission_classes = [IsSupervisorOrAbove]

    @extend_schema(responses=WarningSerializer(many=True))
    def get(self, request):
        return Response(WarningSerializer(Warning.objects.all()[:52], many=True).data)


class WarningDetailView(APIView):
    content_negotiation_class = IgnoreFormatParamNegotiation  # ?format=csv is handled below

    """RdP: the full list. SC: the same generated list filtered to their team (Story 5.5)."""

    permission_classes = [IsSupervisorOrAbove]

    @extend_schema(parameters=[OpenApiParameter("format", str)], responses=OpenApiTypes.OBJECT)
    def get(self, request, week_of):
        if week_of == "latest":
            warning = Warning.objects.first()
            if warning is None:
                return Response(None)
        else:
            warning = get_object_or_404(Warning, week_of=week_of)
        payload = _payload(warning, request.user)
        if request.query_params.get("format") == "csv":
            buffer = io.StringIO()
            fields = [
                "rank", "kind", "full_name", "role", "threshold_days", "area",
                "days_since_last_verified", "delta_days", "supervisor",
            ]
            writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(payload["entries"])
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="warning-{warning.week_of}.csv"'
            return response
        return Response(payload)


class GenerateWarningView(APIView):
    """Manual (re)generation. Idempotent: regenerating a week replaces it."""

    permission_classes = [IsRdpOrAdmin]

    @extend_schema(
        request=None, parameters=[OpenApiParameter("week_of", str)],
        responses=OpenApiTypes.OBJECT,
    )
    def post(self, request):
        raw = request.data.get("week_of") or request.query_params.get("week_of")
        today = clock.today()
        week_of = date.fromisoformat(raw) if raw else today.fromordinal(today.toordinal() - today.weekday())
        if week_of.weekday() != 0:
            raise ValidationError("week_of must be a Monday")
        return Response(_payload(services.generate(week_of), request.user), status=201)
