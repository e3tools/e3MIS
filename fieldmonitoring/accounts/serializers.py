from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from authorization.models import User


class UserSerializer(serializers.ModelSerializer):
    # User ids are strings in this API (they were UUIDs before the MIS merge); clients compare
    # them with ids taken from URLs.
    id = serializers.CharField(read_only=True)
    commune = serializers.CharField(source="commune.name", default=None, read_only=True)
    region = serializers.CharField(source="region.name", default=None, read_only=True)
    supervisor = serializers.CharField(source="supervisor.full_name", default=None, read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "full_name",
            "email",
            "role",
            "commune",
            "region",
            "supervisor",
            "device_class",
            "onboarded_on",
            "phone_number",
            "preferred_language",
        )
        read_only_fields = (
            "id", "username", "full_name", "role", "device_class", "onboarded_on",
        )


class UserSummarySerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "full_name", "role", "device_class")


class EmailOrUsernameTokenSerializer(TokenObtainPairSerializer):
    """Sign-in for the field app and the dashboard.

    MIS users sign in with their email. App builds already in the field send it as ``username``,
    so either key is accepted. Matching is exact, as everywhere else in the MIS.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[self.username_field].required = False
        self.fields["username"] = serializers.CharField(required=False, write_only=True)

    def validate(self, attrs):
        username = attrs.pop("username", None)
        if not attrs.get(self.username_field):
            if not username:
                raise serializers.ValidationError({self.username_field: "This field is required."})
            attrs[self.username_field] = username
        return super().validate(attrs)
