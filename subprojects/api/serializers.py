from rest_framework import serializers

from subprojects.models import Subproject


class SubprojectSerializer(serializers.ModelSerializer):

    class Meta:
        model = Subproject
        fields = '__all__'
