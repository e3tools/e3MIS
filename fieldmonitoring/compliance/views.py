import csv
import io
from dataclasses import asdict
from datetime import timedelta

from django.db import transaction
from django.db.models import Min
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from authorization.models import Role, User
from fieldmonitoring.accounts.permissions import (
    IsAdmin,
    IsSupervisorOrAbove,

    can_view_user,
    has_role,
)
from fieldmonitoring.core.negotiation import IgnoreFormatParamNegotiation
from fieldmonitoring.core import clock
from fieldmonitoring.core.models import ConfigChange, ProgrammeConfig
from fieldmonitoring.registry.models import Worksite, WorksiteStatus
from fieldmonitoring.review.views import queue_for
from fieldmonitoring.visits.models import Visit, VisitState

from . import rules, services
from .models import Pause, RoleThreshold
from .serializers import PauseSerializer, ProgrammeConfigSerializer, ThresholdSerializer

Dict = OpenApiTypes.OBJECT


class MyPresenceView(APIView):
    """Presence card: days since last verified visit against the person's own threshold."""

    permission_classes = [has_role(Role.FT, Role.FC, Role.SC)]

    @extend_schema(responses=Dict)
    def get(self, request):
        return Response(asdict(services.presence(request.user, clock.today())))


class MyQuotaView(APIView):
    permission_classes = [has_role(Role.REGIONAL_SPECIALIST, Role.NATIONAL_SPECIALIST)]

    @extend_schema(responses=Dict)
    def get(self, request):
        user, today = request.user, clock.today()
        if user.role == Role.REGIONAL_SPECIALIST:
            return Response({"kind": "regional", **asdict(services.regional_quota(user, today))})
        return Response({"kind": "national", **asdict(services.national_quota(user, today))})


def team_members(viewer, supervisor_id=None):
    users = User.objects.filter(is_active=True, role__in=[Role.FT, Role.FC])
    if viewer.role == Role.SC:
        return users.filter(supervisor=viewer)
    if supervisor_id:
        return users.filter(supervisor_id=supervisor_id)
    return User.objects.filter(is_active=True, role__in=[Role.FT, Role.FC, Role.SC])


class TeamPresenceView(APIView):
    """Story 5.3. Paused people are shown, never hidden."""

    permission_classes = [IsSupervisorOrAbove]

    @extend_schema(parameters=[OpenApiParameter("supervisor", str)], responses=Dict)
    def get(self, request):
        viewer = request.user
        config, thresholds, today = ProgrammeConfig.get(), RoleThreshold.as_dict(), clock.today()
        members = team_members(viewer, request.query_params.get("supervisor")).select_related(
            "commune"
        )
        rows = [services.team_row(u, today, config, thresholds) for u in members]

        supervisor_id = request.query_params.get("supervisor")
        queue = queue_for(viewer)
        active_sites = Worksite.objects.filter(status=WorksiteStatus.ACTIVE)
        if viewer.role == Role.SC:
            active_sites = active_sites.filter(commune_id=viewer.commune_id)
        elif supervisor_id:
            # RdP/admin looking at one SC's team: scope the tiles to that team too.
            supervisor = get_object_or_404(User, pk=supervisor_id, role=Role.SC)
            queue = Visit.objects.filter(
                state=VisitState.UNVERIFIED, resolved_by__isnull=True, user__supervisor=supervisor
            )
            active_sites = active_sites.filter(commune_id=supervisor.commune_id)
        oldest = queue.aggregate(oldest=Min("checked_in_at"))["oldest"]
        lo, _ = clock.local_day_bounds(today - timedelta(days=6), config)
        visited = (
            Visit.objects.filter(
                worksite__in=active_sites, state=VisitState.VERIFIED, checked_in_at__gte=lo
            )
            .values("worksite_id")
            .distinct()
            .count()
        )
        paused = [r for r in rows if r["paused"]]
        roles = sorted({r["role"] for r in rows})
        return Response({
            "today": today,
            "thresholds": {role: thresholds[role] for role in roles if role in thresholds},
            "review_sla_hours": config.review_sla_hours,
            "stats": {
                "over_threshold": sum(1 for r in rows if r["flagged"]),
                "awaiting_review": queue.count(),
                "oldest_review_at": oldest,
                "worksites_visited_7d": visited,
                "active_worksites": active_sites.count(),
                "paused": len(paused),
                "next_resume_on": min((r["paused_until"] for r in paused), default=None),
            },
            "rows": sorted(rows, key=lambda r: (r["paused"], -r["days_since"])),
        })


class UserPausesView(APIView):
    """BR-4. RdP, admin, or the SC of the person. An SC cannot pause themselves."""

    permission_classes = [IsSupervisorOrAbove]

    def _target(self, request, user_id):
        target = get_object_or_404(User, pk=user_id)
        if not can_view_user(request.user, target):
            raise PermissionDenied()
        return target

    @extend_schema(responses=PauseSerializer(many=True))
    def get(self, request, user_id):
        target = self._target(request, user_id)
        return Response(PauseSerializer(target.pauses.select_related("set_by"), many=True).data)

    @extend_schema(request=PauseSerializer, responses=PauseSerializer)
    def post(self, request, user_id):
        target = self._target(request, user_id)
        data = PauseSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        problem = rules.pause_permission(
            request.user.role, request.user.pk, target.pk, target.supervisor_id
        ) or rules.validate_pause(
            v["starts_on"], v.get("ends_on"), v.get("reason"), ProgrammeConfig.get().max_pause_days
        )
        if problem:
            raise ValidationError({"code": problem.value})
        pause = Pause.objects.create(user=target, set_by=request.user, **v)
        return Response(PauseSerializer(pause).data, status=201)


class CancelPauseView(APIView):
    permission_classes = [IsSupervisorOrAbove]

    @extend_schema(request=None, responses=PauseSerializer)
    def post(self, request, pause_id):
        pause = get_object_or_404(Pause.objects.select_related("user"), pk=pause_id)
        if rules.pause_permission(
            request.user.role, request.user.pk, pause.user_id, pause.user.supervisor_id
        ):
            raise PermissionDenied()
        if pause.cancelled_at is None:
            pause.cancelled_at = clock.now()
            pause.cancelled_by = request.user
            pause.save(update_fields=["cancelled_at", "cancelled_by"])
        return Response(PauseSerializer(pause).data)


def _audit(key, old, new, user):
    if str(old) != str(new):
        ConfigChange.objects.create(key=key, old_value=str(old), new_value=str(new), changed_by=user)


class ThresholdsView(APIView):
    """Story 6.1. Readable by anyone, since people are measured against it; editable by admin."""

    def get_permissions(self):
        return [IsAdmin()] if self.request.method == "PUT" else super().get_permissions()

    def _all(self):
        for role, days in RoleThreshold.LAUNCH_VALUES.items():
            RoleThreshold.objects.get_or_create(role=role, defaults={"days": days})
        return RoleThreshold.objects.select_related("updated_by").order_by("role")

    @extend_schema(responses=ThresholdSerializer(many=True))
    def get(self, request):
        return Response(ThresholdSerializer(self._all(), many=True).data)

    @extend_schema(request=ThresholdSerializer(many=True), responses=ThresholdSerializer(many=True))
    @transaction.atomic
    def put(self, request):
        current = {t.role: t for t in self._all()}
        for item in request.data:
            threshold = current.get(item.get("role"))
            if threshold is None:
                raise ValidationError(f"unknown role {item.get('role')}")
            data = ThresholdSerializer(threshold, data=item, partial=True)
            data.is_valid(raise_exception=True)
            if data.validated_data["days"] < 1:
                raise ValidationError("days must be at least 1")
            _audit(f"threshold.{threshold.role}", threshold.days, data.validated_data["days"], request.user)
            data.save(updated_by=request.user)
        return Response(ThresholdSerializer(self._all(), many=True).data)


class ProgrammeConfigView(APIView):
    def get_permissions(self):
        return [IsAdmin()] if self.request.method == "PUT" else super().get_permissions()

    @extend_schema(responses=ProgrammeConfigSerializer)
    def get(self, request):
        return Response(ProgrammeConfigSerializer(ProgrammeConfig.get()).data)

    @extend_schema(request=ProgrammeConfigSerializer, responses=ProgrammeConfigSerializer)
    @transaction.atomic
    def put(self, request):
        config = ProgrammeConfig.get()
        data = ProgrammeConfigSerializer(config, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        for key, value in data.validated_data.items():
            _audit(f"config.{key}", getattr(config, key), value, request.user)
        data.save(updated_by=request.user)
        return Response(data.data)


class ConfigHistoryView(APIView):
    permission_classes = [has_role(Role.RDP, Role.ADMIN)]

    @extend_schema(responses=Dict)
    def get(self, request):
        return Response([
            {
                "key": c.key, "old_value": c.old_value, "new_value": c.new_value,
                "changed_by": c.changed_by.full_name if c.changed_by else None,
                "changed_at": c.changed_at,
            }
            for c in ConfigChange.objects.select_related("changed_by")[:200]
        ])


class BaselineView(APIView):
    content_negotiation_class = IgnoreFormatParamNegotiation  # ?format=csv is handled below

    """Story 5.6: days since last verified visit per person per week, for threshold review."""

    permission_classes = [has_role(Role.RDP, Role.ADMIN)]

    @extend_schema(
        parameters=[OpenApiParameter("weeks", int), OpenApiParameter("format", str)],
        responses=Dict,
    )
    def get(self, request):
        weeks = max(1, min(int(request.query_params.get("weeks", 8)), 52))
        config, today = ProgrammeConfig.get(), clock.today()
        last_sunday = today - timedelta(days=today.weekday() + 1)
        sundays = [last_sunday - timedelta(weeks=i) for i in reversed(range(weeks))]
        rows = []
        for user in User.objects.filter(is_active=True, role__in=[Role.FT, Role.FC, Role.SC]):
            for sunday in sundays:
                if sunday < user.onboarded_on:
                    continue
                p = services.presence(user, sunday, config)
                rows.append({
                    "week_ending": sunday.isoformat(),
                    "user_id": str(user.id),
                    "full_name": user.full_name,
                    "role": user.role,
                    "days_since_last_verified": p.days_since,
                    "paused": p.paused,
                })
        if request.query_params.get("format") == "csv":
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0]) if rows else ["week_ending"])
            writer.writeheader()
            writer.writerows(rows)
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="baseline.csv"'
            return response
        return Response({"weeks": [s.isoformat() for s in sundays], "rows": rows})


