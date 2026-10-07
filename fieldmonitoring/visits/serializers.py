from rest_framework import serializers

from fieldmonitoring.accounts.serializers import UserSummarySerializer
from fieldmonitoring.registry.serializers import VillageSerializer

from fieldmonitoring.core.models import ProgrammeConfig

from .models import FieldReasonCode, Visit, VisitEvent, VisitFlag, VisitStatus, WorksProgress, is_short_visit

QUEUED_GAP_S = 3600


class ClockEvidenceSerializer(serializers.Serializer):
    """Trusted-clock evidence for a visit recorded offline (core/trusted_clock.py). No wall-clock time."""

    anchor = serializers.CharField(max_length=200)
    anchor_elapsed_ms = serializers.IntegerField(min_value=0)
    elapsed_ms = serializers.IntegerField(min_value=0)
    anchor_boot_id = serializers.CharField(max_length=64)
    boot_id = serializers.CharField(max_length=64)


class CheckInSerializer(serializers.Serializer):
    """No timestamp field: checked_in_at is set by the server (non-negotiable 2).
    Unknown fields, including any client-supplied checked_in_at, are ignored."""

    worksite_id = serializers.UUIDField()
    lat = serializers.FloatField(required=False, allow_null=True, min_value=-90, max_value=90)
    lng = serializers.FloatField(required=False, allow_null=True, min_value=-180, max_value=180)
    accuracy_m = serializers.FloatField(required=False, allow_null=True, min_value=0)
    capture_token = serializers.UUIDField()
    is_mock_location = serializers.BooleanField(default=False)
    idempotency_key = serializers.CharField(max_length=64)
    # Metadata only (Story 2.7): when the client captured a queued submission.
    client_captured_at = serializers.DateTimeField(required=False, allow_null=True)
    clock = ClockEvidenceSerializer(required=False, allow_null=True)


class CheckOutSerializer(serializers.Serializer):
    lat = serializers.FloatField(required=False, allow_null=True, min_value=-90, max_value=90)
    lng = serializers.FloatField(required=False, allow_null=True, min_value=-180, max_value=180)
    accuracy_m = serializers.FloatField(required=False, allow_null=True, min_value=0)
    idempotency_key = serializers.CharField(max_length=64)
    clock = ClockEvidenceSerializer(required=False, allow_null=True)
    # The phone's note of when it queued the check-out: a signal only, never a time.
    client_captured_at = serializers.DateTimeField(required=False, allow_null=True)


class VisitStatusSerializer(serializers.ModelSerializer):
    works_progress = serializers.ChoiceField(choices=WorksProgress.choices)
    issue_reported = serializers.BooleanField(required=False)
    # Accepted from app builds up to 6, which still send the old name. Remove once
    # no phone runs those builds.
    grievance_raised = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = VisitStatus
        fields = ("works_progress", "issue_reported", "issue_description", "grievance_raised", "note", "submitted_at")
        read_only_fields = ("submitted_at",)

    def validate(self, attrs):
        legacy = attrs.pop("grievance_raised", None)
        if "issue_reported" not in attrs:
            if legacy is None:
                raise serializers.ValidationError({"issue_reported": "This field is required."})
            attrs["issue_reported"] = legacy
        description = (attrs.get("issue_description") or "").strip()
        attrs["issue_description"] = description if attrs["issue_reported"] and description else None
        return attrs


class ReasonSerializer(serializers.Serializer):
    reason_code = serializers.ChoiceField(choices=FieldReasonCode.choices)
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=2000)


class ResolveSerializer(serializers.Serializer):
    resolution = serializers.ChoiceField(choices=[("verified", "verified"), ("missed", "missed")])
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=2000)


class FlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitFlag
        fields = ("kind", "detail", "raised_at")


class EventSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.full_name", default=None)

    class Meta:
        model = VisitEvent
        fields = ("event", "from_state", "to_state", "reason", "actor", "at", "note")


class WorksiteRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    code = serializers.CharField()
    village = VillageSerializer()
    is_high_risk = serializers.BooleanField()
    has_coordinate = serializers.SerializerMethodField()

    def get_has_coordinate(self, obj) -> bool:
        return obj.location is not None


def _point(p):
    return {"lat": p.y, "lng": p.x} if p else None


class VisitSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    worksite = WorksiteRefSerializer(read_only=True)
    status = VisitStatusSerializer(read_only=True, default=None)
    flags = FlagSerializer(many=True, read_only=True)
    checkin = serializers.SerializerMethodField()
    checkout = serializers.SerializerMethodField()
    has_photo = serializers.SerializerMethodField()
    awaiting_review = serializers.BooleanField(read_only=True)
    needs_reason = serializers.SerializerMethodField()
    resolved_by = serializers.CharField(source="resolved_by.full_name", default=None)
    queued_submission = serializers.SerializerMethodField()
    short_visit = serializers.SerializerMethodField()

    class Meta:
        model = Visit
        fields = (
            "id", "user", "worksite", "state", "unverified_reason", "checked_in_at",
            "checked_out_at", "time_on_site_s", "checkin", "checkout", "is_mock_location",
            "has_photo", "auto_closed", "status", "flags", "field_reason_code", "field_reason",
            "field_reason_at", "awaiting_review", "needs_reason", "resolved_by", "resolved_at",
            "resolution_note", "client_captured_at", "queued_submission", "short_visit",
            "checkin_received_at", "checkout_received_at", "checkin_time_source", "checkout_time_source",
        )

    def get_checkin(self, obj) -> dict:
        return {
            **(_point(obj.checkin_location) or {"lat": None, "lng": None}),
            "accuracy_m": obj.checkin_accuracy_m,
            "distance_m": obj.checkin_distance_m,
        }

    def get_checkout(self, obj) -> dict | None:
        return _point(obj.checkout_location)

    def get_has_photo(self, obj) -> bool:
        return obj.photo_id is not None

    def get_needs_reason(self, obj) -> bool:
        return obj.awaiting_review and obj.field_reason_code is None

    def get_queued_submission(self, obj) -> bool:
        """Story 3.5: show both times when capture and receipt differ by over an hour."""
        if not obj.client_captured_at:
            return False
        return abs((obj.checked_in_at - obj.client_captured_at).total_seconds()) > QUEUED_GAP_S

    def get_short_visit(self, obj) -> bool:
        """Checked out after less than the configured minutes on site: a warning, never a state change."""
        return is_short_visit(obj, self._short_visit_s())

    def _short_visit_s(self) -> int:
        if not hasattr(self, "_short_s"):
            root = self.root if self.root is not None else self
            if not hasattr(root, "_short_s"):
                root._short_s = ProgrammeConfig.get().short_visit_minutes * 60
            self._short_s = root._short_s
        return self._short_s


class VisitDetailSerializer(VisitSerializer):
    events = EventSerializer(many=True, read_only=True)

    class Meta(VisitSerializer.Meta):
        fields = VisitSerializer.Meta.fields + ("events",)
