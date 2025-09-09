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


class FollowUpEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = 'FollowUpEvent'
        fields = '__all__'


class FollowUpEventDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = 'FollowUpEventDependency'
        fields = '__all__'


class FollowUpEventResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = 'FollowUpEventResponse'
        fields = '__all__'
