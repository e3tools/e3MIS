from django.db import models
from django.utils.translation import gettext as _
from django.contrib.auth.models import Group

from src.settings import AUTH_USER_MODEL


class TrackableObject(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    groups = models.ManyToManyField(Group, verbose_name=_('Custom Fields'), related_name="trackable_objects",
                                    blank=True)
    jsonForm = models.JSONField(help_text="JSON schema + options for the form", default=list)


class FollowUpEvent(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    jsonForm = models.JSONField(help_text="JSON schema + options for the form", default=list)


class TrackableObjectResponse(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    trackable_object = models.ForeignKey(TrackableObject, on_delete=models.CASCADE)
    jsonForm = models.JSONField(help_text="JSON response schema", default=list)


class FollowUpEventResponse(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    follow_up_event = models.ForeignKey(FollowUpEvent, on_delete=models.CASCADE)
    trackable_object_response = models.ForeignKey(TrackableObjectResponse, on_delete=models.CASCADE)
