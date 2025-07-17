from rest_framework import serializers

from subprojects.models import Subproject, SubprojectCustomField


class SubprojectSerializer(serializers.ModelSerializer):

    class Meta:
        model = Subproject
        fields = '__all__'


class SubprojectCustomFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubprojectCustomField
        fields = '__all__'
