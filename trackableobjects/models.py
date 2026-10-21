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


class VersionedSchemaMixin(models.Model):
    """A form template whose schema version goes up each time its jsonForm changes.

    Answers record the schema_version they were filled against, so an answer filled offline on
    an older version can be recognised when it syncs.
    """
    schema_version = models.PositiveIntegerField(default=1, editable=False)

    class Meta:
        abstract = True

    @classmethod
    def from_db(cls, db, field_names, values):
        obj = super().from_db(db, field_names, values)
        obj._loaded_json_form = obj.__dict__.get("jsonForm")
        return obj

    def save(self, *args, **kwargs):
        loaded = getattr(self, "_loaded_json_form", None)
        if self.pk and loaded is not None and loaded != self.jsonForm:
            self.schema_version += 1
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = {*kwargs["update_fields"], "schema_version"}
        super().save(*args, **kwargs)
        self._loaded_json_form = self.jsonForm


class SyncedAnswerMixin(models.Model):
    """An answer (record or follow-up) that the field app can create offline and sync later.

    - client_uuid: generated on the phone; uploading the same item twice creates nothing new.
    - version: goes up each time the answers change, to detect a stale offline edit.
    - schema_version: the template's schema_version when the answer was created.
    """
    client_uuid = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    version = models.PositiveIntegerField(default=1, editable=False)
    schema_version = models.PositiveIntegerField(null=True, blank=True, editable=False)

    class Meta:
        abstract = True

    def _template(self):
        raise NotImplementedError

    @classmethod
    def from_db(cls, db, field_names, values):
        obj = super().from_db(db, field_names, values)
        obj._loaded_json_form = obj.__dict__.get("jsonForm")
        return obj

    def save(self, *args, **kwargs):
        loaded = getattr(self, "_loaded_json_form", None)
        extra = set()
        if self.pk is None and self.schema_version is None:
            template = self._template()
            if template is not None:
                self.schema_version = template.schema_version
                extra.add("schema_version")
        elif self.pk and loaded is not None and loaded != self.jsonForm:
            self.version += 1
            extra.add("version")
        if extra and kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = {*kwargs["update_fields"], *extra}
        super().save(*args, **kwargs)
        self._loaded_json_form = self.jsonForm


class TrackableObject(VersionedSchemaMixin, models.Model):
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
    # Lifecycle (lifecycle.py): ordered stages a record goes through, e.g.
    # [{"key": "works", "label": "Travaux"}, …]. The first one is where new records start.
    # Empty: no lifecycle, every linked follow-up event is always available.
    stages = models.JSONField(default=list, blank=True)
    # A record of this type is a worksite for visits (lifecycle.create_worksite).
    creates_worksite = models.BooleanField(default=False)

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


class FollowUpEvent(VersionedSchemaMixin, models.Model):
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
    # Record stages in which this event can be filled (keys of TrackableObject.stages). Empty: any.
    stages = models.JSONField(default=list, blank=True)
    # How an answer moves the record to another stage, first match wins:
    # [{"field": "phase", "operator": "equals", "value": "Travaux achevés", "to": "acceptance"}].
    stage_rules = models.JSONField(default=list, blank=True)

    class Meta(VersionedSchemaMixin.Meta):
        abstract = False
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


class TrackableObjectInstance(SyncedAnswerMixin, models.Model):
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
    # Current lifecycle stage (a key of trackable_object.stages); blank when the type has none.
    stage = models.CharField(max_length=32, blank=True, default="")
    # The worksite visit it was filled in (visit_forms.py).
    visit_key = models.CharField(max_length=64, blank=True, default="", db_index=True)
    visit = models.ForeignKey("visits.Visit", null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="form_records")

    class Meta:
        indexes = [models.Index(fields=["updated_at"])]

    def _template(self):
        return self.trackable_object

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


class FollowUpEventResponse(SyncedAnswerMixin, models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    follow_up_event = models.ForeignKey(FollowUpEvent, on_delete=models.CASCADE, related_name="responses", )
    trackable_object_instance = models.ForeignKey(TrackableObjectInstance, blank=True, null=True,
                                                  on_delete=models.SET_NULL,
                                                  related_name="follow_up_responses", )
    jsonForm = models.JSONField(help_text="JSON response schema", default=list)
    # The worksite visit it was filled in (visit_forms.py).
    visit_key = models.CharField(max_length=64, blank=True, default="", db_index=True)
    visit = models.ForeignKey("visits.Visit", null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="form_responses")

    class Meta:
        indexes = [models.Index(fields=["updated_at"])]

    def _template(self):
        return self.follow_up_event

    @property
    def identifier(self):
        if self.follow_up_event.identifier_field in self.jsonForm:
            return self.jsonForm[self.follow_up_event.identifier_field]
        return date(self.created_at, "N j, y")

    @property
    def display_id(self):
        return f"{FOLLOW_UP_EVENT_ID_PREFIX}-{self.id}" if self.id else ""


class RecordStageChange(models.Model):
    """Every lifecycle move of a record: by a follow-up answer (``response``) or by a person (reopen)."""
    instance = models.ForeignKey(TrackableObjectInstance, on_delete=models.CASCADE, related_name="stage_changes")
    from_stage = models.CharField(max_length=32, blank=True)
    to_stage = models.CharField(max_length=32)
    response = models.ForeignKey(FollowUpEventResponse, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="+")
    changed_by = models.ForeignKey(AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    changed_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-changed_at", "-id"]
