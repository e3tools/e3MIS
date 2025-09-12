from rest_framework import serializers

from trackableobjects.models import (
    TrackableObject, TrackableObjectInstance,
    FollowUpEvent, FollowUpEventDependency,
    FollowUpEventResponse
)


class TrackableObjectSerializer(serializers.ModelSerializer):

    class Meta:
        model = TrackableObject
        fields = [
            'id', 'name', 'description',
            'identifier_field', 'jsonForm', 'groups',
            'created_by', 'created_at', 'updated_at',
        ]


class TrackableObjectInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackableObjectInstance
        fields = [
            'id', 'trackable_object', 'jsonForm',
            'administrative_units', 'groups', 'created_by',
            'created_at', 'updated_at', 'identifier',
        ]


class FollowUpEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowUpEvent
        fields = [
            'id', 'name', 'description',
            'identifier_field', 'is_one_off', 'trackable_object',
            'jsonForm', 'groups', 'created_by',
            'created_at', 'updated_at',
        ]


class FollowUpEventDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowUpEventDependency
        fields = '__all__'


class FollowUpEventResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowUpEventResponse
        fields = [
            'id', 'follow_up_event', 'trackable_object_instance',
            'jsonForm', 'created_by', 'created_at',
            'updated_at', 'identifier',
        ]
