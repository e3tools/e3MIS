from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            'username', 'email', 'is_field_agent',
            'administrative_unit', 'username', 'first_name',
            'last_name', 'email', 'is_staff', 'is_active',
            'date_joined', 'last_login',
        ]
