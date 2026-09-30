from rest_framework import serializers

from fieldmonitoring.core.models import ProgrammeConfig

from .models import Pause, RoleThreshold


class PauseSerializer(serializers.ModelSerializer):
    set_by = serializers.CharField(source="set_by.full_name", read_only=True)
    cancelled_by = serializers.CharField(source="cancelled_by.full_name", default=None, read_only=True)
    # Required, never open-ended (BR-4).
    ends_on = serializers.DateField(required=True, allow_null=True)
    reason = serializers.CharField(required=True, allow_blank=True)

    class Meta:
        model = Pause
        fields = (
            "id", "starts_on", "ends_on", "reason", "set_by", "set_at", "cancelled_at", "cancelled_by",
        )
        read_only_fields = ("id", "set_by", "set_at", "cancelled_at", "cancelled_by")


class ThresholdSerializer(serializers.ModelSerializer):
    updated_by = serializers.CharField(source="updated_by.full_name", default=None, read_only=True)
    launch_value = serializers.SerializerMethodField()

    class Meta:
        model = RoleThreshold
        fields = ("role", "days", "launch_value", "updated_by", "updated_at")
        read_only_fields = ("role", "updated_by", "updated_at")

    def get_launch_value(self, obj) -> int:
        return RoleThreshold.LAUNCH_VALUES[obj.role]


class ProgrammeConfigSerializer(serializers.ModelSerializer):
    updated_by = serializers.CharField(source="updated_by.full_name", default=None, read_only=True)

    class Meta:
        model = ProgrammeConfig
        exclude = ("id",)
        read_only_fields = ("updated_by", "updated_at")

    def validate_timezone(self, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError("Unknown timezone")
        return value

    def validate_working_days(self, value):
        if not isinstance(value, list) or not all(isinstance(d, int) and 0 <= d <= 6 for d in value):
            raise serializers.ValidationError("A list of weekday numbers, 0 = Monday")
        return sorted(set(value))
