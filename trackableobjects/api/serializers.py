from rest_framework import serializers

from trackableobjects.models import TrackableObject, TrackableObjectInstance


class TrackableObjectSerializer(serializers.ModelSerializer):

    class Meta:
        model = TrackableObject
        fields = '__all__'


class TrackableObjectInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackableObjectInstance
        fields = '__all__'
