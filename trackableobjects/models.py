from django.db import models
from django.utils.translation import gettext as _
from django.contrib.auth.models import Group

from administrativelevels.models import AdministrativeUnit
from src.settings import AUTH_USER_MODEL


class TrackableObject(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    groups = models.ManyToManyField(Group, verbose_name=_('Groups'), related_name="trackable_objects",
                                    blank=True)
    jsonForm = models.JSONField(help_text="JSON schema + options for the form", default=list)


class FollowUpEvent(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    trackable_object = models.ForeignKey(TrackableObject, on_delete=models.CASCADE, related_name="follow_up_events", )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    groups = models.ManyToManyField(Group, verbose_name=_('Groups'), related_name="follow_up_events",
                                    blank=True)
    jsonForm = models.JSONField(help_text="JSON schema + options for the form", default=list)


class FollowUpEventDependency(models.Model):
    parent = models.ForeignKey(FollowUpEvent, on_delete=models.CASCADE, related_name="dependencies_parents")
    child = models.ForeignKey(FollowUpEvent, on_delete=models.CASCADE, related_name="dependencies_children")


class TrackableObjectInstance(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    trackable_object = models.ForeignKey(TrackableObject, on_delete=models.CASCADE, related_name="instances", )
    groups = models.ManyToManyField(Group, verbose_name=_('Groups'), related_name="trackable_object_instances",
                                    blank=True)
    administrative_units = models.ManyToManyField(AdministrativeUnit, verbose_name=_('Administrative units'),
                                                  blank=True, related_name="trackable_object_instances", )
    jsonForm = models.JSONField(help_text="JSON response schema", default=list)


class FollowUpEventResponse(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    follow_up_event = models.ForeignKey(FollowUpEvent, on_delete=models.CASCADE, related_name="responses", )
    trackable_object_instance = models.ForeignKey(TrackableObjectInstance, blank=True, null=True,
                                                  on_delete=models.SET_NULL,
                                                  related_name="trackable_object_instances", )
    jsonForm = models.JSONField(help_text="JSON response schema", default=list)
