from django.db import models
from django.template.defaultfilters import date
from django.utils.translation import gettext as _
from django.contrib.auth.models import Group

from administrativelevels.models import AdministrativeUnit
from src.settings import AUTH_USER_MODEL


class TrackableObject(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    identifier_field = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    groups = models.ManyToManyField(Group, verbose_name=_('Groups'), related_name="trackable_objects",
                                    blank=True)
    jsonForm = models.JSONField(help_text="JSON schema + options for the form", default=list)

    def __str__(self):
        return self.name


class FollowUpEvent(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    identifier_field = models.CharField(max_length=255, null=True, blank=True)
    trackable_object = models.ForeignKey(TrackableObject, on_delete=models.CASCADE, related_name="follow_up_events", )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    is_one_off = models.BooleanField(default=False)
    groups = models.ManyToManyField(Group, verbose_name=_('Groups'), related_name="follow_up_events",
                                    blank=True)
    jsonForm = models.JSONField(help_text="JSON schema + options for the form", default=list)

    def __str__(self):
        return self.name


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

    @property
    def identifier(self):
        if self.trackable_object.identifier_field in self.jsonForm:
            return self.jsonForm[self.trackable_object.identifier_field]
        return date(self.created_at, "N j, y")


class FollowUpEventResponse(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    follow_up_event = models.ForeignKey(FollowUpEvent, on_delete=models.CASCADE, related_name="responses", )
    trackable_object_instance = models.ForeignKey(TrackableObjectInstance, blank=True, null=True,
                                                  on_delete=models.SET_NULL,
                                                  related_name="follow_up_responses", )
    jsonForm = models.JSONField(help_text="JSON response schema", default=list)

    @property
    def identifier(self):
        if self.follow_up_event.identifier_field in self.jsonForm:
            return self.jsonForm[self.follow_up_event.identifier_field]
        return date(self.created_at, "N j, y")
