"""CDD cycle: a community goes through phases → activities → tasks; MIS forms are the evidence.

Concept: ``CDD_MODULE_CONCEPT.md`` in the workspace. The cycle is designed in the MIS (a
``CycleTemplate``), each community follows it in a ``Cycle``. Task status is computed from the
forms tagged with the cycle and the task (``progress.py``); only decisions a person makes (mark a
task without forms done, close without form, not applicable) are stored, in ``TaskProgress``.

Form answers point at their cycle with ``cdd_cycle`` and at their task with ``cdd_task_key``: the
key, not a foreign key, so answers keep their task when the template is edited.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class CycleTemplate(models.Model):
    """The CDD cycle as a programme runs it. One active template in practice."""

    name = models.CharField(_("name"), max_length=255)
    description = models.TextField(_("description"), blank=True)
    # Goes up when the tree changes, so the app knows to fetch it again.
    version = models.PositiveIntegerField(default=1, editable=False)
    is_active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("cycle template")

    def __str__(self):
        return self.name

    def tasks(self):
        return Task.objects.filter(activity__phase__template=self)

    def bump_version(self):
        CycleTemplate.objects.filter(pk=self.pk).update(version=models.F("version") + 1)
        self.refresh_from_db(fields=["version", "updated_at"])


class Phase(models.Model):
    template = models.ForeignKey(CycleTemplate, on_delete=models.CASCADE, related_name="phases")
    order = models.PositiveIntegerField(default=0)
    name = models.CharField(_("name"), max_length=255)
    description = models.TextField(_("description"), blank=True)
    planned_days = models.PositiveIntegerField(_("planned duration (days)"), null=True, blank=True)

    class Meta:
        ordering = ["template", "order", "id"]

    def __str__(self):
        return self.name


class Activity(models.Model):
    phase = models.ForeignKey(Phase, on_delete=models.CASCADE, related_name="activities")
    order = models.PositiveIntegerField(default=0)
    name = models.CharField(_("name"), max_length=255)
    description = models.TextField(_("description"), blank=True)

    class Meta:
        ordering = ["phase", "order", "id"]
        verbose_name_plural = _("activities")

    def __str__(self):
        return self.name


class TaskKind(models.TextChoices):
    FORM = "form", _("Form")
    MEETING = "meeting", _("Meeting")
    CHECKLIST = "checklist", _("Checklist")
    MANUAL = "manual", _("Manual")


class Task(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="tasks")
    order = models.PositiveIntegerField(default=0)
    # Stable across template edits: progress and form answers refer to the task by its key.
    key = models.SlugField(_("key"), max_length=64)
    name = models.CharField(_("name"), max_length=255)
    instructions = models.TextField(_("instructions"), blank=True)
    kind = models.CharField(_("kind"), max_length=16, choices=TaskKind.choices, default=TaskKind.FORM)
    # Optional tasks count neither for progress nor for the current phase.
    required = models.BooleanField(_("required"), default=True)
    # Due date = cycle start + this many days. Empty: no due date.
    planned_offset_days = models.PositiveIntegerField(_("due (days after the cycle starts)"), null=True, blank=True)
    # Roles who may mark it (authorization.Role values); empty: any facilitator of the cycle.
    completer_roles = models.JSONField(default=list, blank=True)
    # Tasks expected before this one. Doing it earlier gives a warning, never a block (CDD-7).
    depends_on = models.ManyToManyField("self", symmetrical=False, blank=True, related_name="followed_by")

    class Meta:
        ordering = ["activity", "order", "id"]

    def __str__(self):
        return self.name

    @property
    def template(self):
        return self.activity.phase.template

    def clean(self):
        super().clean()
        if self.activity_id and self.key:
            clash = Task.objects.filter(activity__phase__template=self.activity.phase.template_id, key=self.key)
            if clash.exclude(pk=self.pk).exists():
                raise ValidationError({"key": _("Another task of this cycle already uses this key.")})


class TaskForm(models.Model):
    """A form whose answers are the evidence of a task: a record type or a follow-up event."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="forms")
    trackable_object = models.ForeignKey(
        "trackableobjects.TrackableObject", null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    follow_up_event = models.ForeignKey(
        "trackableobjects.FollowUpEvent", null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    min_count = models.PositiveIntegerField(_("answers needed"), default=1)
    required = models.BooleanField(_("required"), default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(trackable_object__isnull=False, follow_up_event__isnull=True)
                           | Q(trackable_object__isnull=True, follow_up_event__isnull=False)),
                name="cdd_taskform_one_form",
            ),
        ]

    def __str__(self):
        return str(self.trackable_object or self.follow_up_event)

    @property
    def ref(self) -> str:
        """``to:<id>`` or ``fe:<id>``, how progress.py and the app name a form."""
        if self.trackable_object_id:
            return f"to:{self.trackable_object_id}"
        return f"fe:{self.follow_up_event_id}"


class CycleStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    SUSPENDED = "suspended", _("Suspended")
    CLOSED = "closed", _("Closed")


class Cycle(models.Model):
    """One community going through the template. One active cycle per community at a time."""

    template = models.ForeignKey(CycleTemplate, on_delete=models.PROTECT, related_name="cycles")
    template_version = models.PositiveIntegerField(default=1)
    community = models.ForeignKey(
        "administrativelevels.AdministrativeUnit", on_delete=models.PROTECT, related_name="cdd_cycles",
        verbose_name=_("community"),
    )
    number = models.PositiveIntegerField(_("cycle number"), default=1)
    started_on = models.DateField(_("started on"))
    planned_end = models.DateField(_("planned end"), null=True, blank=True)
    status = models.CharField(max_length=16, choices=CycleStatus.choices, default=CycleStatus.ACTIVE)
    facilitators = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="cdd_cycles")
    client_uuid = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    version = models.PositiveIntegerField(default=1, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["community__name", "-number"]
        constraints = [
            models.UniqueConstraint(fields=["community", "number"], name="cdd_cycle_number"),
            models.UniqueConstraint(fields=["community"], condition=Q(status="active"), name="cdd_one_active_cycle"),
        ]

    def __str__(self):
        return f"{self.community} — {_('cycle')} {self.number}"


class ManualStatus(models.TextChoices):
    """What a person decided about a task. Form evidence is never stored here (CDD-1)."""

    DONE = "done", _("Done")
    CLOSED_WITHOUT_FORM = "closed_without_form", _("Closed without form")
    NOT_APPLICABLE = "not_applicable", _("Not applicable")


class TaskProgress(models.Model):
    """A person's decision on a task of a cycle. Created when there is one."""

    cycle = models.ForeignKey(Cycle, on_delete=models.CASCADE, related_name="task_progress")
    task_key = models.SlugField(max_length=64)
    manual_status = models.CharField(max_length=24, choices=ManualStatus.choices, blank=True)
    note = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # Server time (non-negotiable 2).
    decided_at = models.DateTimeField(null=True, blank=True)
    client_uuid = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    version = models.PositiveIntegerField(default=1, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["cycle", "task_key"], name="cdd_one_progress_per_task")]

    def __str__(self):
        return f"{self.cycle} · {self.task_key}: {self.manual_status or '-'}"


class CycleEventKind(models.TextChoices):
    STARTED = "started", _("Cycle started")
    SUSPENDED = "suspended", _("Cycle suspended")
    CLOSED = "closed", _("Cycle closed")
    REOPENED = "reopened", _("Cycle reopened")
    TASK_DONE = "task_done", _("Task marked done")
    TASK_CLOSED_WITHOUT_FORM = "task_closed_without_form", _("Task closed without form")
    TASK_NOT_APPLICABLE = "task_not_applicable", _("Task not applicable")
    TASK_RESET = "task_reset", _("Task decision withdrawn")


class CycleEvent(models.Model):
    """History of a cycle, like RecordStageChange for records."""

    cycle = models.ForeignKey(Cycle, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=32, choices=CycleEventKind.choices)
    task_key = models.SlugField(max_length=64, blank=True)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-at", "-id"]

    def __str__(self):
        return f"{self.cycle} · {self.get_kind_display()}"
