from rest_framework import serializers

from administrativelevels.models import AdministrativeUnit

from .models import HighRiskFlagChange, ProvisionalCoordinate, Worksite


class VillageSerializer(serializers.ModelSerializer):
    """A village is an MIS administrative unit (usually at the programme's village level)."""

    id = serializers.CharField(read_only=True)  # ids are strings in this API, as before the merge

    class Meta:
        model = AdministrativeUnit
        fields = ("id", "name")


class WorksiteSerializer(serializers.ModelSerializer):
    village = VillageSerializer(read_only=True)
    commune = serializers.CharField(source="commune.name", read_only=True)
    has_coordinate = serializers.SerializerMethodField()

    class Meta:
        model = Worksite
        fields = (
            "id", "name", "code", "village", "commune", "latitude", "longitude",
            "tolerance_m", "is_high_risk", "status", "is_provisional", "has_coordinate",
        )

    def get_has_coordinate(self, obj) -> bool:
        return obj.location is not None


class WorksiteListItemSerializer(WorksiteSerializer):
    """A worksite with staleness. For specialists this is a ranking, never an assignment (R3)."""

    last_verified_on = serializers.DateField(allow_null=True)
    days_since_last_visit = serializers.IntegerField(allow_null=True)
    # The requesting user's own most recent visit here, in any state, so the app can
    # say "visited today at 09:12 · verified" and avoid accidental repeat visits.
    my_last_visit_at = serializers.DateTimeField(allow_null=True)
    my_last_visit_state = serializers.CharField(allow_null=True)
    my_visits_today = serializers.IntegerField()

    class Meta(WorksiteSerializer.Meta):
        fields = WorksiteSerializer.Meta.fields + (
            "last_verified_on", "days_since_last_visit",
            "my_last_visit_at", "my_last_visit_state", "my_visits_today",
        )


class NearbyWorksiteSerializer(WorksiteListItemSerializer):
    distance_m = serializers.IntegerField(allow_null=True)
    my_recent_visit_on = serializers.DateField(allow_null=True)
    rotation_repeat = serializers.BooleanField()

    class Meta(WorksiteListItemSerializer.Meta):
        fields = WorksiteListItemSerializer.Meta.fields + (
            "distance_m", "my_recent_visit_on", "rotation_repeat",
        )


class ProvisionalWorksiteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    village_id = serializers.IntegerField()


class HighRiskProposalSerializer(serializers.Serializer):
    to_value = serializers.BooleanField()
    # Free text, mandatory. Not a dropdown (BR-15).
    reason = serializers.CharField(min_length=10)


class HighRiskChangeSerializer(serializers.ModelSerializer):
    worksite = WorksiteSerializer(read_only=True)
    proposed_by = serializers.CharField(source="proposed_by.full_name")
    approved_by = serializers.CharField(source="approved_by.full_name", default=None)

    class Meta:
        model = HighRiskFlagChange
        fields = (
            "id", "worksite", "to_value", "reason", "proposed_by", "proposed_at",
            "status", "approved_by", "decided_at", "review_due_on",
        )


class ProvisionalCoordinateSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(source="location.y")
    longitude = serializers.FloatField(source="location.x")
    captured_by = serializers.CharField(source="captured_by.full_name")
    visit_id = serializers.UUIDField(source="visit.id", default=None)
    has_photo = serializers.SerializerMethodField()

    class Meta:
        model = ProvisionalCoordinate
        fields = (
            "id", "latitude", "longitude", "accuracy_m", "captured_by", "captured_at",
            "visit_id", "has_photo", "status",
        )

    def get_has_photo(self, obj) -> bool:
        return bool(obj.visit and obj.visit.photo_id)
