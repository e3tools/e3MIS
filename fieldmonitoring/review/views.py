"""BR-10 / Story 3.4: the unverified-visit review queue.

Resolving decides whether a visit counts. It is a data decision, not a performance
process (DEC-6). Nothing happens to a visit when the 72-hour target passes.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from authorization.models import Role
from fieldmonitoring.accounts.permissions import IsSupervisorOrAbove, can_resolve
from fieldmonitoring.visits.models import UnverifiedReason, Visit, VisitState
from fieldmonitoring.visits.serializers import ResolveSerializer, VisitSerializer
from fieldmonitoring.visits.state_machine import Event, apply
from fieldmonitoring.visits.views import VISIT_RELATED


def queue_for(viewer):
    visits = Visit.objects.filter(state=VisitState.UNVERIFIED, resolved_by__isnull=True).exclude(
        user=viewer
    )
    if viewer.role == Role.SC:
        return visits.filter(user__supervisor=viewer)
    if viewer.role == Role.RDP:
        return visits.filter(user__supervisor__isnull=True)
    return visits  # admin


class ReviewQueueView(APIView):
    permission_classes = [IsSupervisorOrAbove]

    @extend_schema(responses=VisitSerializer(many=True))
    def get(self, request):
        visits = (
            queue_for(request.user)
            .select_related(*VISIT_RELATED)
            .prefetch_related("flags")
            .order_by("checked_in_at")
        )
        return Response(VisitSerializer(visits, many=True).data)


class ResolveView(APIView):
    permission_classes = [IsSupervisorOrAbove]

    @extend_schema(request=ResolveSerializer, responses=VisitSerializer)
    @transaction.atomic
    def post(self, request, visit_id):
        visit = get_object_or_404(
            Visit.objects.select_for_update().select_related("user"), pk=visit_id
        )
        if not can_resolve(request.user, visit):
            raise PermissionDenied("This visit is not in your review queue.")
        if not visit.awaiting_review:
            raise ValidationError({"code": "not_awaiting_review"})
        data = ResolveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        note = (data.validated_data.get("note") or "").strip() or None
        if visit.unverified_reason == UnverifiedReason.MOCK_LOCATION and not note:
            # "Open case": it needs a conversation, not a click. Record what was decided.
            raise ValidationError({"note": "A mock-location case needs a note from the conversation."})
        event = (
            Event.RESOLVE_VERIFIED
            if data.validated_data["resolution"] == "verified"
            else Event.RESOLVE_MISSED
        )
        apply(visit, event, actor=request.user, note=note)
        visit = Visit.objects.select_related(*VISIT_RELATED).get(pk=visit.pk)
        return Response(VisitSerializer(visit).data)
