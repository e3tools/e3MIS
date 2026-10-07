from datetime import timedelta

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from administrativelevels.models import AdministrativeUnit
from authorization.models import Role
from fieldmonitoring.accounts.permissions import IsRdpOrAdmin, RecordsVisits, has_role
from fieldmonitoring.compliance import rules
from fieldmonitoring.compliance.services import last_verified_by_worksite, worksite_scope
from fieldmonitoring.core import clock
from fieldmonitoring.core.geography import villages_under
from fieldmonitoring.core.models import ProgrammeConfig
from fieldmonitoring.visits.services import earlier_verified_days, make_point

from .models import (
    DecisionStatus,
    HighRiskFlagChange,
    ProvisionalCoordinate,
    Worksite,
)
from .serializers import (
    HighRiskChangeSerializer,
    HighRiskProposalSerializer,
    NearbyWorksiteSerializer,
    ProvisionalCoordinateSerializer,
    ProvisionalWorksiteSerializer,
    VillageSerializer,
    WorksiteListItemSerializer,
    WorksiteSerializer,
)


def _with_staleness(worksites, latest, today):
    for w in worksites:
        last = latest.get(w.id)
        w.last_verified_on = clock.local_date(last) if last else None
        w.days_since_last_visit = (today - w.last_verified_on).days if last else None
    return worksites


def _with_my_last_visit(worksites, user, today):
    """Attach the user's own latest visit (any state) and today's visit count per worksite."""
    from fieldmonitoring.visits.models import Visit

    ids = [w.id for w in worksites]
    start, end = clock.local_day_bounds(today)
    latest, today_counts = {}, {}
    for worksite_id, at, state in (
        Visit.objects.filter(user=user, worksite_id__in=ids)
        .order_by("worksite_id", "-checked_in_at")
        .values_list("worksite_id", "checked_in_at", "state")
    ):
        latest.setdefault(worksite_id, (at, state))
        if start <= at < end:
            today_counts[worksite_id] = today_counts.get(worksite_id, 0) + 1
    for w in worksites:
        at, state = latest.get(w.id, (None, None))
        w.my_last_visit_at, w.my_last_visit_state = at, state
        w.my_visits_today = today_counts.get(w.id, 0)
    return worksites


def _staleness_key(w):
    # Never visited first, then oldest; high-risk breaks ties (Story 4.4).
    never = w.days_since_last_visit is None
    return (not never, -(w.days_since_last_visit or 0), not w.is_high_risk, w.name)


class MyWorksitesView(APIView):
    """Story 2.1 (facilitators: own visits) and Story 4.4 (specialists: anyone's visits)."""

    permission_classes = [RecordsVisits]

    @extend_schema(responses=WorksiteListItemSerializer(many=True))
    def get(self, request):
        user = request.user
        worksites = list(worksite_scope(user))
        latest = last_verified_by_worksite(
            [w.id for w in worksites], None if user.is_specialist else user
        )
        today = clock.today()
        items = sorted(_with_staleness(worksites, latest, today), key=_staleness_key)
        _with_my_last_visit(items, user, today)
        return Response(WorksiteListItemSerializer(items, many=True).data)


class NearbyWorksitesView(APIView):
    """Story 2.2. Nearest active worksites in scope, plus unmapped sites in the same villages."""

    permission_classes = [RecordsVisits]

    @extend_schema(
        parameters=[
            OpenApiParameter("lat", float, required=True),
            OpenApiParameter("lng", float, required=True),
            OpenApiParameter("radius_m", int),
            OpenApiParameter("exclude", str),
        ],
        responses=NearbyWorksiteSerializer(many=True),
    )
    def get(self, request):
        config = ProgrammeConfig.get()
        try:
            point = make_point(request.query_params["lat"], request.query_params["lng"])
            radius = int(request.query_params.get("radius_m", config.nearby_radius_m))
        except (KeyError, ValueError):
            raise ValidationError("lat, lng (and optional integer radius_m) are required")
        radius = min(radius, 20_000)
        user = request.user
        scope = worksite_scope(user)
        if exclude := request.query_params.get("exclude"):
            scope = scope.exclude(pk=exclude)
        near = list(
            scope.filter(location__dwithin=(point, D(m=radius)))
            .annotate(distance=Distance("location", point))
            .order_by("distance")
        )
        villages = {w.village_id for w in near}
        unmapped = list(scope.filter(location__isnull=True, village_id__in=villages))
        items = near + unmapped

        today = clock.today(config)
        latest = last_verified_by_worksite(
            [w.id for w in items], None if user.is_specialist else user
        )
        _with_staleness(items, latest, today)
        _with_my_last_visit(items, user, today)
        now = clock.now()
        for w in items:
            w.distance_m = round(w.distance.m) if getattr(w, "distance", None) is not None else None
            # BR-7 preview, so the check-in screen can say plainly whether a repeat visit
            # counts as a rotation exception. High-risk sites are exempt.
            earlier = earlier_verified_days(user, w, now, config.tz) if user.is_specialist else []
            recent = [d for d in earlier if (today - d).days <= config.rotation_window_days]
            w.my_recent_visit_on = max(recent, default=None)
            w.rotation_repeat = (
                rules.rotation_repeat(
                    user.role, w.is_high_risk, today, earlier, config.rotation_window_days
                )
                is not None
            )
        return Response(NearbyWorksiteSerializer(items, many=True).data)


def villages_in_scope(user):
    """The villages a user may pick: their region for regional specialists, else their commune."""
    if user.role == Role.REGIONAL_SPECIALIST and user.region_id:
        return villages_under(user.region)
    if user.commune_id:
        return villages_under(user.commune)
    return AdministrativeUnit.objects.none()


class VillagesView(APIView):
    """Villages in the user's scope, for 'not listed — add a worksite'."""

    permission_classes = [RecordsVisits]

    @extend_schema(responses=VillageSerializer(many=True))
    def get(self, request):
        villages = villages_in_scope(request.user)
        return Response(VillageSerializer(villages.order_by("name"), many=True).data)


class ProvisionalWorksiteView(APIView):
    """'Not listed — add a worksite'. Created without a coordinate, pending admin confirmation."""

    permission_classes = [RecordsVisits]

    @extend_schema(request=ProvisionalWorksiteSerializer, responses=WorksiteSerializer)
    def post(self, request):
        data = ProvisionalWorksiteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        village = get_object_or_404(AdministrativeUnit, pk=data.validated_data["village_id"])
        if not villages_in_scope(request.user).filter(pk=village.pk).exists():
            return Response({"detail": "village_out_of_scope"}, status=status.HTTP_400_BAD_REQUEST)
        worksite = Worksite.objects.create(
            name=data.validated_data["name"],
            village=village,
            is_provisional=True,
            created_by=request.user,
        )
        return Response(WorksiteSerializer(worksite).data, status=status.HTTP_201_CREATED)


# --- High-risk flag (BR-15, Story 6.3) ------------------------------------------------


class HighRiskProposeView(APIView):
    permission_classes = [has_role(Role.NATIONAL_SPECIALIST)]

    @extend_schema(request=HighRiskProposalSerializer, responses=HighRiskChangeSerializer)
    def post(self, request, worksite_id):
        worksite = get_object_or_404(Worksite, pk=worksite_id)
        data = HighRiskProposalSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        change = HighRiskFlagChange.objects.create(
            worksite=worksite, proposed_by=request.user, **data.validated_data
        )
        return Response(HighRiskChangeSerializer(change).data, status=status.HTTP_201_CREATED)


class HighRiskListView(APIView):
    permission_classes = [has_role(Role.NATIONAL_SPECIALIST, Role.RDP, Role.ADMIN)]

    @extend_schema(
        parameters=[OpenApiParameter("status", str)], responses=HighRiskChangeSerializer(many=True)
    )
    def get(self, request):
        changes = HighRiskFlagChange.objects.select_related(
            "worksite__village", "worksite__commune", "proposed_by", "approved_by"
        )
        if s := request.query_params.get("status"):
            changes = changes.filter(status=s)
        return Response(HighRiskChangeSerializer(changes[:200], many=True).data)


class HighRiskDecideView(APIView):
    """Not effective until the RdP approves. Setter and approver must differ (DEC-5)."""

    permission_classes = [IsRdpOrAdmin]

    @extend_schema(request=None, responses=HighRiskChangeSerializer)
    @transaction.atomic
    def post(self, request, change_id, decision):
        if decision not in ("approve", "reject"):
            raise ValidationError("decision must be approve or reject")
        change = get_object_or_404(HighRiskFlagChange.objects.select_for_update(), pk=change_id)
        if change.status != DecisionStatus.PENDING:
            raise ValidationError("already decided")
        if change.proposed_by_id == request.user.pk:
            raise ValidationError("the proposer cannot approve their own change")
        change.approved_by = request.user
        change.decided_at = clock.now()
        if decision == "approve":
            change.status = DecisionStatus.CONFIRMED
            change.review_due_on = clock.today() + timedelta(days=91)  # one quarter ahead
            worksite = change.worksite
            worksite.is_high_risk = change.to_value
            worksite.high_risk_review_due_on = change.review_due_on if change.to_value else None
            worksite.save(update_fields=["is_high_risk", "high_risk_review_due_on"])
        else:
            change.status = DecisionStatus.REJECTED
        change.save()
        return Response(HighRiskChangeSerializer(change).data)


# --- Coordinate confirmation (Story 6.4) -----------------------------------------------


def coordinate_scope(user):
    """Worksites whose coordinates a user may confirm: all for an admin; for a communal supervisor,
    those in their commune or created by their team (sub-project forms, Brice's answer 1)."""
    if user.role == Role.ADMIN:
        return Worksite.objects.all()
    if user.role == Role.SC:
        mine = Q(created_by__supervisor=user) | Q(created_by=user)
        if user.commune_id:
            mine |= Q(commune_id=user.commune_id)
        return Worksite.objects.filter(mine)
    return Worksite.objects.none()


CanConfirmCoordinates = has_role(Role.ADMIN, Role.SC)


class PendingCoordinatesView(APIView):
    """Worksites whose geofence is not live yet. This queue is when verification becomes true."""

    permission_classes = [CanConfirmCoordinates]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        pending = (
            ProvisionalCoordinate.objects.filter(
                status=DecisionStatus.PENDING, worksite__in=coordinate_scope(request.user)
            )
            .select_related("worksite__village", "worksite__commune", "captured_by", "visit")
        )
        groups = {}
        for coord in pending:
            groups.setdefault(coord.worksite, []).append(coord)
        result = []
        for worksite, coords in groups.items():
            lat = sum(c.location.y for c in coords) / len(coords)
            lng = sum(c.location.x for c in coords) / len(coords)
            centre = make_point(lat, lng)
            spread = (
                ProvisionalCoordinate.objects.filter(pk__in=[c.pk for c in coords])
                .annotate(d=Distance("location", centre))
                .order_by("-d")
                .first()
                .d.m
            )
            result.append({
                "worksite": WorksiteSerializer(worksite).data,
                "captures": ProvisionalCoordinateSerializer(coords, many=True).data,
                "spread_m": round(spread),
            })
        return Response({
            "count": len(result),
            "worksites_without_coordinate": coordinate_scope(request.user).filter(
                location__isnull=True, status="active"
            ).count(),
            "results": result,
        })


class CoordinateDecideView(APIView):
    permission_classes = [CanConfirmCoordinates]

    @extend_schema(request=None, responses=WorksiteSerializer)
    @transaction.atomic
    def post(self, request, coordinate_id, decision):
        if decision not in ("confirm", "reject"):
            raise ValidationError("decision must be confirm or reject")
        coord = get_object_or_404(
            ProvisionalCoordinate.objects.select_for_update().filter(worksite__in=coordinate_scope(request.user)),
            pk=coordinate_id,
        )
        now = clock.now()
        worksite = coord.worksite
        if decision == "confirm":
            worksite.location = coord.location
            worksite.is_provisional = False
            worksite.save(update_fields=["location", "is_provisional"])
            # The other captures for this worksite are superseded.
            worksite.provisional_coordinates.filter(status=DecisionStatus.PENDING).exclude(
                pk=coord.pk
            ).update(status=DecisionStatus.REJECTED, decided_by=request.user, decided_at=now)
            coord.status = DecisionStatus.CONFIRMED
        else:
            coord.status = DecisionStatus.REJECTED
        coord.decided_by = request.user
        coord.decided_at = now
        coord.save()
        return Response(WorksiteSerializer(worksite).data)
