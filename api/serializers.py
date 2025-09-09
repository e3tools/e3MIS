from rest_framework import serializers


class TokenCreateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True)
    scopes = serializers.ListField(child=serializers.CharField(), required=False)
    ttl_hours = serializers.IntegerField(required=False, min_value=1)


class TokenOutSerializer(serializers.Serializer):
    token = serializers.CharField()
    id = serializers.CharField()
    name = serializers.CharField()
    scopes = serializers.ListField(child=serializers.CharField())
    expires_at = serializers.DateTimeField(allow_null=True)
