from rest_framework import serializers

from administrativelevels.models import AdministrativeUnit


class AdministrativeUnitModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdministrativeUnit
        fields = '__all__'
