"""Where a community stands in its CDD cycle. Every status, progress figure and warning comes from here.

Rules (tests in ``tests/fieldmonitoring/test_cdd.py`` are named after them):

- CDD-1  A task with required forms is *done* when each required form has at least ``min_count``
         answers tagged with the cycle and the task; *in progress* while some evidence exists; *to do*
         otherwise. The form is the evidence: nobody marks such a task done by hand (services.py).
- CDD-2  A task without required forms is *done* when a person marks it; evidence alone only makes
         it *in progress*.
- CDD-3  *Closed without form* and *not applicable* are a person's decision with a reason, and win
         over the evidence. A not-applicable task leaves the counts; a task closed without form
         counts as completed and is also counted apart, for the dashboards.
- CDD-4  Progress = completed required tasks / required tasks that apply, per phase and per cycle.
         Optional tasks never count.
- CDD-5  The current phase is the first phase with a required task that applies and is not completed.
- CDD-6  A task of an active cycle is overdue the day after its due date (cycle start + the task's
         offset) while it is not completed. On the due date itself it is not.
- CDD-7  A task started (evidence or a decision) while a task it depends on is not completed gets a
         warning. Never a block: the tool warns, it does not enforce (non-negotiable 5).
- CDD-8  An active cycle with no activity for ``ProgrammeConfig.cdd_inactive_days`` days or more is
         flagged inactive. Activity = the start, a tagged answer, a decision or a cycle event.

Suspended and closed cycles keep their progress but have no overdue tasks and are never inactive.
Dates are programme dates (fieldmonitoring.core.clock), never the device's.

The calculation itself (``evaluate``) works on plain data, so the field app can mirror it (as
``trackableobjects/lifecycle.py`` is mirrored by the app's ``lifecycle.ts``); ``state()`` loads a
cycle from the database and evaluates it.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.db.models import Count, Max

from fieldmonitoring.core import clock
from fieldmonitoring.core.models import ProgrammeConfig

from .models import CycleStatus, ManualStatus

TODO = "todo"
IN_PROGRESS = "in_progress"
DONE = ManualStatus.DONE.value
CLOSED_WITHOUT_FORM = ManualStatus.CLOSED_WITHOUT_FORM.value
NOT_APPLICABLE = ManualStatus.NOT_APPLICABLE.value

COMPLETED = frozenset({DONE, CLOSED_WITHOUT_FORM})
SETTLED = COMPLETED | {NOT_APPLICABLE}


@dataclass(frozen=True)
class FormNeed:
    ref: str  # "to:<trackable object id>" or "fe:<follow-up event id>" (TaskForm.ref)
    min_count: int = 1
    required: bool = True


@dataclass(frozen=True)
class TaskSpec:
    key: str
    name: str
    phase_id: int
    required: bool = True
    offset_days: int | None = None
    depends_on: tuple[str, ...] = ()
    forms: tuple[FormNeed, ...] = ()

    @property
    def required_forms(self) -> tuple[FormNeed, ...]:
        return tuple(f for f in self.forms if f.required)


@dataclass(frozen=True)
class PhaseSpec:
    id: int
    name: str


@dataclass
class Snapshot:
    """A cycle as plain data: the template (phases and tasks in order) and what happened."""

    status: str
    started_on: date
    phases: list[PhaseSpec]
    tasks: list[TaskSpec]
    evidence: dict[str, dict[str, int]] = field(default_factory=dict)  # task key → form ref → answers
    decisions: dict[str, str] = field(default_factory=dict)  # task key → ManualStatus value
    last_activity: date | None = None


@dataclass
class TaskState:
    key: str
    name: str
    phase_id: int
    required: bool
    status: str
    due_on: date | None
    overdue_days: int
    waiting_on: list[str]  # CDD-7: keys of the tasks it depends on that are not completed
    evidence: dict[str, int]


@dataclass
class PhaseState:
    id: int
    name: str
    completed: int
    total: int

    @property
    def progress(self) -> float | None:
        return self.completed / self.total if self.total else None


@dataclass
class CycleState:
    status: str
    phases: list[PhaseState]
    tasks: list[TaskState]
    completed: int
    total: int
    current_phase_id: int | None
    last_activity: date
    idle_days: int
    inactive: bool

    @property
    def progress(self) -> float | None:
        return self.completed / self.total if self.total else None

    @property
    def overdue_count(self) -> int:
        return sum(1 for t in self.tasks if t.overdue_days)

    @property
    def closed_without_form_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == CLOSED_WITHOUT_FORM)

    def task(self, key: str) -> TaskState | None:
        return next((t for t in self.tasks if t.key == key), None)


def task_status(spec: TaskSpec, evidence: dict[str, int], decision: str = "") -> str:
    """CDD-1, CDD-2, CDD-3."""
    if decision in (CLOSED_WITHOUT_FORM, NOT_APPLICABLE, DONE):
        return decision
    needed = spec.required_forms
    if needed and all(evidence.get(f.ref, 0) >= f.min_count for f in needed):
        return DONE
    if any(evidence.get(f.ref, 0) for f in spec.forms):
        return IN_PROGRESS
    return TODO


def due_on(spec: TaskSpec, started_on: date) -> date | None:
    return started_on + timedelta(days=spec.offset_days) if spec.offset_days is not None else None


def overdue_days(status: str, due: date | None, today: date, cycle_status: str = CycleStatus.ACTIVE) -> int:
    """CDD-6: days past the due date, 0 when not overdue."""
    if cycle_status != CycleStatus.ACTIVE or due is None or status in SETTLED:
        return 0
    return max(0, (today - due).days)


def evaluate(snapshot: Snapshot, today: date, inactive_days: int) -> CycleState:
    statuses = {
        spec.key: task_status(spec, snapshot.evidence.get(spec.key, {}), snapshot.decisions.get(spec.key, ""))
        for spec in snapshot.tasks
    }
    tasks = []
    for spec in snapshot.tasks:
        status = statuses[spec.key]
        due = due_on(spec, snapshot.started_on)
        waiting = []
        if status != TODO:  # CDD-7
            waiting = [k for k in spec.depends_on if k in statuses and statuses[k] not in SETTLED]
        tasks.append(TaskState(
            key=spec.key, name=spec.name, phase_id=spec.phase_id, required=spec.required, status=status,
            due_on=due, overdue_days=overdue_days(status, due, today, snapshot.status), waiting_on=waiting,
            evidence=dict(snapshot.evidence.get(spec.key, {})),
        ))

    # CDD-4, CDD-5
    counted = [t for t in tasks if t.required and t.status != NOT_APPLICABLE]
    phases, current = [], None
    for phase in snapshot.phases:
        own = [t for t in counted if t.phase_id == phase.id]
        completed = sum(1 for t in own if t.status in COMPLETED)
        phases.append(PhaseState(id=phase.id, name=phase.name, completed=completed, total=len(own)))
        if current is None and completed < len(own):
            current = phase.id

    # CDD-8
    last = max(filter(None, [snapshot.started_on, snapshot.last_activity]))
    idle = max(0, (today - last).days)
    return CycleState(
        status=snapshot.status, phases=phases, tasks=tasks,
        completed=sum(1 for t in counted if t.status in COMPLETED), total=len(counted),
        current_phase_id=current, last_activity=last, idle_days=idle,
        inactive=snapshot.status == CycleStatus.ACTIVE and idle >= inactive_days,
    )


# --- Database ------------------------------------------------------------------------------------


def template_specs(template) -> tuple[list[PhaseSpec], list[TaskSpec]]:
    from .models import Phase

    phases, tasks = [], []
    for phase in Phase.objects.filter(template=template).prefetch_related(
        "activities__tasks__forms", "activities__tasks__depends_on"
    ):
        phases.append(PhaseSpec(id=phase.id, name=phase.name))
        for activity in phase.activities.all():
            for task in activity.tasks.all():
                tasks.append(TaskSpec(
                    key=task.key, name=task.name, phase_id=phase.id, required=task.required,
                    offset_days=task.planned_offset_days,
                    depends_on=tuple(sorted(d.key for d in task.depends_on.all())),
                    forms=tuple(FormNeed(f.ref, f.min_count, f.required) for f in task.forms.all()),
                ))
    return phases, tasks


def snapshot(cycle, config: ProgrammeConfig | None = None) -> Snapshot:
    from trackableobjects.models import FollowUpEventResponse, TrackableObjectInstance

    config = config or ProgrammeConfig.get()
    phases, tasks = template_specs(cycle.template)
    evidence: dict[str, dict[str, int]] = {}
    tagged = [
        (TrackableObjectInstance.objects.filter(cdd_cycle=cycle), "trackable_object_id", "to"),
        (FollowUpEventResponse.objects.filter(cdd_cycle=cycle), "follow_up_event_id", "fe"),
    ]
    moments = []
    for queryset, form_field, prefix in tagged:
        queryset = queryset.exclude(cdd_task_key="")
        for row in queryset.values("cdd_task_key", form_field).annotate(n=Count("id")):
            evidence.setdefault(row["cdd_task_key"], {})[f"{prefix}:{row[form_field]}"] = row["n"]
        moments.append(queryset.aggregate(last=Max("updated_at"))["last"])
    decisions = dict(cycle.task_progress.exclude(manual_status="").values_list("task_key", "manual_status"))
    moments.append(cycle.task_progress.aggregate(last=Max("decided_at"))["last"])
    moments.append(cycle.events.aggregate(last=Max("at"))["last"])
    moments = [clock.local_date(m, config) for m in moments if m is not None]
    return Snapshot(
        status=cycle.status, started_on=cycle.started_on, phases=phases, tasks=tasks, evidence=evidence,
        decisions=decisions, last_activity=max(moments) if moments else None,
    )


def state(cycle, today: date | None = None, config: ProgrammeConfig | None = None) -> CycleState:
    config = config or ProgrammeConfig.get()
    return evaluate(snapshot(cycle, config), today or clock.today(config), config.cdd_inactive_days)
