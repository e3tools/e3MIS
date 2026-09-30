from datetime import timedelta

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from fieldmonitoring.accounts.permissions import RecordsVisits, can_view_visit
from fieldmonitoring.compliance.services import worksite_scope
from fieldmonitoring.core import clock

from . import services
from .models import Photo, Visit, VisitState
from .serializers import (
    CheckInSerializer,
    CheckOutSerializer,
    ReasonSerializer,
    VisitDetailSerializer,
    VisitSerializer,
    VisitStatusSerializer,
)

VISIT_RELATED = ("user", "worksite__village", "status", "resolved_by")


def error(exc: services.VisitError, code=status.HTTP_409_CONFLICT):
    return Response({"code": exc.code, "detail": str(exc)}, status=code)


def own_visit(request, visit_id) -> Visit:
    return get_object_or_404(
        Visit.objects.select_related(*VISIT_RELATED), pk=visit_id, user=request.user
    )


class CaptureTokenView(APIView):
    """Requested before the camera opens (BR-11)."""

    permission_classes = [RecordsVisits]

    @extend_schema(
        request=None,
        responses=inline_serializer(
            "CaptureToken", {"token": serializers.UUIDField(), "expires_at": serializers.DateTimeField()}
        ),
    )
    def post(self, request):
        token = services.issue_capture_token(request.user)
        return Response({"token": token.token, "expires_at": token.expires_at}, status=201)


class PhotoUploadView(APIView):
    permission_classes = [RecordsVisits]
    parser_classes = [MultiPartParser]

    @extend_schema(
        request=inline_serializer(
            "PhotoUpload", {"capture_token": serializers.UUIDField(), "file": serializers.ImageField()}
        ),
        responses=inline_serializer("PhotoUploaded", {"photo_id": serializers.UUIDField()}),
    )
    def post(self, request):
        file = request.FILES.get("file")
        token = request.data.get("capture_token")
        if not file or not token:
            return Response({"code": "missing_fields"}, status=400)
        try:
            photo = services.upload_photo(request.user, token, file)
        except services.VisitError as exc:
            return error(exc, status.HTTP_400_BAD_REQUEST)
        return Response({"photo_id": photo.id}, status=201)


class PhotoView(APIView):
    """Photos are served through an authorised endpoint, never as public media."""

    @extend_schema(responses={(200, "image/jpeg"): bytes})
    def get(self, request, visit_id):
        visit = get_object_or_404(Visit.objects.select_related("user", "photo"), pk=visit_id)
        if not can_view_visit(request.user, visit):
            raise PermissionDenied()
        if not visit.photo:
            raise Http404
        try:
            handle = visit.photo.file.open("rb")
        except (FileNotFoundError, OSError):
            # The record exists but the file is gone (e.g. stored on an instance's
            # disk before object storage was configured).
            return Response({"code": "photo_unavailable"}, status=404)
        response = FileResponse(handle, content_type="image/jpeg")
        # Evidence never changes (blobs are immutable); let the browser keep it, privately.
        response["Cache-Control"] = "private, max-age=86400"
        return response


class CheckInView(APIView):
    permission_classes = [RecordsVisits]

    @extend_schema(request=CheckInSerializer, responses=VisitSerializer)
    def post(self, request):
        data = CheckInSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        worksite = get_object_or_404(worksite_scope(request.user), pk=v.pop("worksite_id"))
        try:
            visit, created = services.check_in(
                request.user, services.CheckIn(worksite=worksite, **v)
            )
        except services.VisitError as exc:
            return error(exc, status.HTTP_400_BAD_REQUEST)
        visit = Visit.objects.select_related(*VISIT_RELATED).get(pk=visit.pk)
        return Response(
            VisitSerializer(visit).data, status=status.HTTP_201_CREATED if created else 200
        )


class VisitStatusView(APIView):
    permission_classes = [RecordsVisits]

    @extend_schema(request=VisitStatusSerializer, responses=VisitStatusSerializer)
    def post(self, request, visit_id):
        visit = own_visit(request, visit_id)
        data = VisitStatusSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            services.submit_status(visit, **data.validated_data)
        except services.VisitError as exc:
            return error(exc)
        return Response(VisitStatusSerializer(visit.status).data)


class CheckOutView(APIView):
    permission_classes = [RecordsVisits]

    @extend_schema(request=CheckOutSerializer, responses=VisitSerializer)
    def post(self, request, visit_id):
        visit = own_visit(request, visit_id)
        data = CheckOutSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            visit = services.check_out(visit, **data.validated_data)
        except services.VisitError as exc:
            return error(exc)
        visit = Visit.objects.select_related(*VISIT_RELATED).get(pk=visit.pk)
        return Response(VisitSerializer(visit).data)


class ReasonView(APIView):
    permission_classes = [RecordsVisits]

    @extend_schema(request=ReasonSerializer, responses=VisitSerializer)
    def post(self, request, visit_id):
        visit = own_visit(request, visit_id)
        data = ReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            visit = services.submit_reason(
                visit, code=data.validated_data["reason_code"], note=data.validated_data.get("note")
            )
        except services.VisitError as exc:
            return error(exc)
        return Response(VisitSerializer(visit).data)


class MyVisitsView(APIView):
    permission_classes = [RecordsVisits]

    @extend_schema(responses=VisitSerializer(many=True))
    def get(self, request):
        since = clock.now() - timedelta(days=30)
        visits = (
            Visit.objects.filter(user=request.user)
            .filter(checked_in_at__gte=since)
            .select_related(*VISIT_RELATED)
            .prefetch_related("flags")
        )
        return Response(VisitSerializer(visits[:100], many=True).data)


class OpenVisitView(APIView):
    """The visit the user is currently on, if any: checked in, not checked out, not auto-closed."""

    permission_classes = [RecordsVisits]

    @extend_schema(responses=VisitSerializer)
    def get(self, request):
        visit = (
            Visit.objects.filter(
                user=request.user,
                checked_out_at__isnull=True,
                auto_closed=False,
                state__in=[VisitState.IN_PROGRESS, VisitState.UNVERIFIED],
            )
            .select_related(*VISIT_RELATED)
            .first()
        )
        return Response(VisitSerializer(visit).data if visit else None)


class VisitDetailView(APIView):
    @extend_schema(responses=VisitDetailSerializer)
    def get(self, request, visit_id):
        visit = get_object_or_404(
            Visit.objects.select_related(*VISIT_RELATED).prefetch_related("flags", "events__actor"),
            pk=visit_id,
        )
        if not can_view_visit(request.user, visit):
            raise PermissionDenied()
        return Response(VisitDetailSerializer(visit).data)


class MyVisitHistoryView(APIView):
    """The field user's own visit history, paged, newest first. `?worksite=<id>` filters."""

    permission_classes = [RecordsVisits]

    @extend_schema(
        parameters=[
            OpenApiParameter("worksite", str),
            OpenApiParameter("limit", int),
            OpenApiParameter("offset", int),
        ],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request):
        from fieldmonitoring.compliance.profile_views import _page

        visits = Visit.objects.filter(user=request.user)
        if worksite := request.query_params.get("worksite"):
            visits = visits.filter(worksite_id=worksite)
        return Response(_page(request, visits))
