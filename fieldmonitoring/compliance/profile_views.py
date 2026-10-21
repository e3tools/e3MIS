"""Supervision drill-downs: a person's profile, their worksites and their visit history,
and a worksite's history. Read-only views for the dashboard."""

from dataclasses import asdict
from datetime import timedelta

from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from authorization.models import FIELD_STAFF_ROLES, Role, User
from fieldmonitoring.accounts.permissions import (
    IsSupervisorOrAbove,
    can_view_user,
    visible_visits,
    visible_worksites,
)
from fieldmonitoring.core import clock
from fieldmonitoring.core.models import ProgrammeConfig
from fieldmonitoring.registry.models import WorksiteAssignment
from fieldmonitoring.registry.serializers import WorksiteSerializer
from fieldmonitoring.visits.models import Visit, VisitState
from fieldmonitoring.visits.serializers import VisitSerializer
from fieldmonitoring.visits.views import VISIT_RELATED

from . import services
from .models import RoleThreshold

PAGE_DEFAULT, PAGE_MAX = 50, 200


def _page(request, queryset):
    try:
        limit = min(max(int(request.query_params.get("limit", PAGE_DEFAULT)), 1), PAGE_MAX)
        offset = max(int(request.query_params.get("offset", 0)), 0)
    except ValueError:
        limit, offset = PAGE_DEFAULT, 0
    visits = queryset.select_related(*VISIT_RELATED).prefetch_related("flags")
    return {
        "count": queryset.count(),
        "limit": limit,
        "offset": offset,
        "results": VisitSerializer(visits.order_by("-checked_in_at")[offset : offset + limit], many=True).data,
    }


PAGING = [OpenApiParameter("limit", int), OpenApiParameter("offset", int)]


def _viewable_user(request, user_id) -> User:
    user = get_object_or_404(User.objects.select_related("commune", "region", "supervisor"), pk=user_id)
    if not can_view_user(request.user, user):
        raise PermissionDenied()
    return user


class UserProfileView(APIView):
    """Profile header for one person: who they are, presence or quota, visit counts."""

    permission_classes = [IsSupervisorOrAbove]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, user_id):
        user = _viewable_user(request, user_id)
        today = clock.today()
        visits = Visit.objects.filter(user=user)
        counts = visits.aggregate(
            total=Count("id"),
            verified=Count("id", filter=Q(state=VisitState.VERIFIED)),
            unverified=Count("id", filter=Q(state=VisitState.UNVERIFIED)),
            missed=Count("id", filter=Q(state=VisitState.MISSED)),
            awaiting_review=Count("id", filter=Q(state=VisitState.UNVERIFIED, resolved_by__isnull=True)),
            last_visit_at=Max("checked_in_at"),
        )
        body = {
            "user": {
                "id": str(user.id),
                "username": user.username,
                "full_name": user.full_name,
                "email": user.email,
                "phone_number": user.phone_number,
                "role": user.role,
                "commune": user.commune.name if user.commune else None,
                "region": user.region.name if user.region else None,
                "supervisor": user.supervisor.full_name if user.supervisor else None,
                "supervisor_id": str(user.supervisor_id) if user.supervisor_id else None,
                "device_class": user.device_class,
                "onboarded_on": user.onboarded_on,
                "is_active": user.is_active,
            },
            "visits": counts,
            "presence": None,
            "quota": None,
        }
        if user.role in FIELD_STAFF_ROLES:
            body["presence"] = asdict(
                services.presence(user, today, ProgrammeConfig.get(), RoleThreshold.as_dict())
            )
        elif user.role == Role.REGIONAL_SPECIALIST:
            body["quota"] = {"kind": "regional", **asdict(services.regional_quota(user, today))}
        elif user.role == Role.NATIONAL_SPECIALIST:
            body["quota"] = {"kind": "national", **asdict(services.national_quota(user, today))}
        return Response(body)


class UserWorksitesView(APIView):
    """Worksites assigned to a person (in force today), with their own visit counts there.
    Specialists have no assignments, so their list is the worksites they have visited."""

    permission_classes = [IsSupervisorOrAbove]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, user_id):
        user = _viewable_user(request, user_id)
        today = clock.today()
        assigned_ids = services.assigned_worksite_ids(user, today)
        assignments = {
            a.worksite_id: a.assigned_on
            for a in WorksiteAssignment.objects.filter(user=user, worksite_id__in=assigned_ids)
        }
        stats = {
            row["worksite_id"]: row
            for row in Visit.objects.filter(user=user)
            .values("worksite_id")
            .annotate(
                visits=Count("id"),
                verified=Count("id", filter=Q(state=VisitState.VERIFIED)),
                last_visit_at=Max("checked_in_at"),
                last_verified_at=Max("checked_in_at", filter=Q(state=VisitState.VERIFIED)),
            )
        }
        ids = set(assigned_ids) | set(stats)
        rows = []
        for worksite in visible_worksites(request.user).filter(id__in=ids):
            s = stats.get(worksite.id, {})
            last_verified = s.get("last_verified_at")
            rows.append({
                **WorksiteSerializer(worksite).data,
                "assigned": worksite.id in assigned_ids,
                "assigned_on": assignments.get(worksite.id),
                "visits": s.get("visits", 0),
                "verified": s.get("verified", 0),
                "last_visit_at": s.get("last_visit_at"),
                "days_since_last_verified": (today - clock.local_date(last_verified)).days if last_verified else None,
            })
        # Never-visited first, then the stalest (same order the facilitator sees).
        rows.sort(key=lambda r: (r["days_since_last_verified"] is not None, -(r["days_since_last_verified"] or 0)))
        return Response(rows)


class UserVisitsView(APIView):
    """A person's visit history, newest first. `?worksite=<id>` narrows it to one worksite."""

    permission_classes = [IsSupervisorOrAbove]

    @extend_schema(parameters=[OpenApiParameter("worksite", str), *PAGING], responses=OpenApiTypes.OBJECT)
    def get(self, request, user_id):
        user = _viewable_user(request, user_id)
        visits = Visit.objects.filter(user=user)
        if worksite := request.query_params.get("worksite"):
            visits = visits.filter(worksite_id=worksite)
        return Response(_page(request, visits))


class WorksiteDetailView(APIView):
    """One worksite: registry data, who is assigned, and visit counts."""

    permission_classes = [IsSupervisorOrAbove]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, worksite_id):
        worksite = get_object_or_404(visible_worksites(request.user), pk=worksite_id)
        today = clock.today()
        in_force = WorksiteAssignment.objects.filter(worksite=worksite, assigned_on__lte=today).filter(
            Q(unassigned_on__isnull=True) | Q(unassigned_on__gt=today)
        ).select_related("user")
        visits = visible_visits(request.user).filter(worksite=worksite)
        last_verified = visits.filter(state=VisitState.VERIFIED).aggregate(at=Max("checked_in_at"))["at"]
        since = clock.local_day_bounds(today - timedelta(days=27))[0]
        return Response({
            "worksite": {
                **WorksiteSerializer(worksite).data,
                "high_risk_review_due_on": worksite.high_risk_review_due_on,
            },
            "assigned": [
                {
                    "user_id": str(a.user_id),
                    "full_name": a.user.full_name,
                    "role": a.user.role,
                    "assigned_on": a.assigned_on,
                }
                for a in in_force
            ],
            "visits": {
                "total": visits.count(),
                "verified_last_4_weeks": visits.filter(state=VisitState.VERIFIED, checked_in_at__gte=since).count(),
                "awaiting_review": visits.filter(state=VisitState.UNVERIFIED, resolved_by__isnull=True).count(),
                "last_verified_at": last_verified,
                "days_since_last_verified": (today - clock.local_date(last_verified)).days if last_verified else None,
            },
        })


class WorksiteVisitsView(APIView):
    """Everyone's visits to one worksite that the viewer may see, newest first."""

    permission_classes = [IsSupervisorOrAbove]

    @extend_schema(parameters=PAGING, responses=OpenApiTypes.OBJECT)
    def get(self, request, worksite_id):
        worksite = get_object_or_404(visible_worksites(request.user), pk=worksite_id)
        return Response(_page(request, visible_visits(request.user).filter(worksite=worksite)))
