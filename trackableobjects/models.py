from django.db import models
from django.template.defaultfilters import date
from django.utils.translation import gettext as _
from django.contrib.auth.models import Group

from administrativelevels.models import AdministrativeUnit
from src.settings import AUTH_USER_MODEL

COLOR_TOKENS = [
    ("amber", "Amber"),
    ("green", "Green"),
    ("blue", "Blue"),
    ("purple", "Purple"),
    ("coral", "Coral"),
    ("teal", "Teal"),
    ("indigo", "Indigo"),
    ("pink", "Pink"),
    ("brown", "Brown"),
    ("slate", "Slate"),
]

COLOR_MAP = {
    "amber":  {"tint": "#fff8e1", "solid": "#e0a800"},
    "green":  {"tint": "#e8f8ef", "solid": "#27ae60"},
    "blue":   {"tint": "#eaf4fb", "solid": "#3498db"},
    "purple": {"tint": "#f3e5f8", "solid": "#8e44ad"},
    "coral":  {"tint": "#fde8e3", "solid": "#d35400"},
    "teal":   {"tint": "#e0f5f4", "solid": "#16a085"},
    "indigo": {"tint": "#e8ebf7", "solid": "#3f51b5"},
    "pink":   {"tint": "#fce4ec", "solid": "#c2185b"},
    "brown":  {"tint": "#efebe9", "solid": "#795548"},
    "slate":  {"tint": "#eceff1", "solid": "#546e7a"},
}

# UI-only prefixes used to build a human-readable display id (e.g. "TO-45").
# These do NOT replace the database primary key — they are purely presentational,
# so that a TrackableObject and a FollowUpEvent (or their instances/responses)
# never look identical just because they happen to share a numeric id.
TRACKABLE_OBJECT_ID_PREFIX = "TO"
FOLLOW_UP_EVENT_ID_PREFIX = "FE"


class TrackableObject(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    identifier_field = models.CharField(max_length=255, null=True, blank=True)
    icon = models.CharField(max_length=64, default="fa-cube",
                            help_text="Font Awesome free (solid) identifier, e.g. 'fa-home'")
    color = models.CharField(max_length=16, default="slate", choices=COLOR_TOKENS,
                             help_text="One of the 10 approved color tokens")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    groups = models.ManyToManyField(Group, verbose_name=_('Groups'), related_name="trackable_objects",
                                    blank=True)
    jsonForm = models.JSONField(help_text="JSON schema + options for the form", default=list)

    @property
    def color_tint(self):
        return COLOR_MAP.get(self.color, COLOR_MAP["slate"])["tint"]

    @property
    def color_solid(self):
        return COLOR_MAP.get(self.color, COLOR_MAP["slate"])["solid"]

    @property
    def display_id(self):
        return f"{TRACKABLE_OBJECT_ID_PREFIX}-{self.id}" if self.id else ""

    def __str__(self):
        return self.name


class FollowUpEvent(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    identifier_field = models.CharField(max_length=255, null=True, blank=True)
    trackable_objects = models.ManyToManyField(TrackableObject, through='FollowUpEventTrackableObject',
                                                  related_name="follow_up_events", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    is_one_off = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    groups = models.ManyToManyField(Group, verbose_name=_('Groups'), related_name="follow_up_events",
                                    blank=True)
    jsonForm = models.JSONField(help_text="JSON schema + options for the form", default=list)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    @property
    def trackable_objects_names(self):
        names = [obj.name for obj in self.trackable_objects.all()]
        return ", ".join(names)

    @property
    def display_id(self):
        return f"{FOLLOW_UP_EVENT_ID_PREFIX}-{self.id}" if self.id else ""


class FollowUpEventTrackableObject(models.Model):
    follow_up_event = models.ForeignKey(FollowUpEvent, on_delete=models.CASCADE)
    trackable_object = models.ForeignKey(TrackableObject, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('follow_up_event', 'trackable_object')

    def __str__(self):
        return f"{self.follow_up_event.name} - {self.trackable_object.name}"


class FollowUpEventDependency(models.Model):
    parent = models.ForeignKey(FollowUpEvent, on_delete=models.CASCADE, related_name="dependencies_parents")
    child = models.ForeignKey(FollowUpEvent, on_delete=models.CASCADE, related_name="dependencies_children")

    def __str__(self):
        return "{} depends on  {}".format(self.child.name, self.parent.name)


class TrackableObjectInstance(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    trackable_object = models.ForeignKey(TrackableObject, on_delete=models.CASCADE, related_name="instances", )
    groups = models.ManyToManyField(Group, verbose_name=_('Groups'), related_name="trackable_object_instances",
                                    blank=True)
    administrative_units = models.ManyToManyField(AdministrativeUnit, verbose_name=_('Administrative units'),
                                                  blank=True, related_name="trackable_object_instances", )
    restrict_by_administrative_units = models.BooleanField(default=True,
                                                           verbose_name=_('Restrict by administrative units'))
    jsonForm = models.JSONField(help_text="JSON response schema", default=list)

    @property
    def identifier(self):
        if self.trackable_object.identifier_field in self.jsonForm:
            return self.jsonForm[self.trackable_object.identifier_field]
        return date(self.created_at, "N j, y")

    @property
    def display_id(self):
        return f"{TRACKABLE_OBJECT_ID_PREFIX}-{self.id}" if self.id else ""

    def __str__(self):
        return "{}".format(self.identifier)


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

    @property
    def display_id(self):
        return f"{FOLLOW_UP_EVENT_ID_PREFIX}-{self.id}" if self.id else ""
