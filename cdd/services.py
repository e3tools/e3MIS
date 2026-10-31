"""Starting, suspending, closing and reopening cycles, and a person's decisions on tasks.

Every change goes through here and leaves a CycleEvent. Times are server time (non-negotiable 2).

- CDD-9  A cycle belongs to one community: a unit at ``ProgrammeConfig.cdd_community_level`` (the
         village level when unset; without either, a unit with no children). A community has one
         active cycle at a time; cycles are numbered 1, 2, … per community.
- CDD-10 Suspending, closing and reopening a cycle need a reason.
- CDD-3  Closing a task without form or marking it not applicable needs a reason.
- CDD-1  A task with required forms cannot be marked done: its forms are the evidence.
- CDD-11 Starting cycles for several communities at once gives each one the facilitators chosen
         plus, when asked, the FT and FC attached to the community or to a unit above it.
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Max
from django.utils.translation import gettext as _

from administrativelevels.models import AdministrativeUnit
from authorization.models import CustomUser, Role
from fieldmonitoring.core import clock
from fieldmonitoring.core.models import ProgrammeConfig

from .models import Cycle, CycleEvent, CycleEventKind, CycleStatus, ManualStatus, Task, TaskProgress

DECISION_EVENTS = {
    ManualStatus.DONE: CycleEventKind.TASK_DONE,
    ManualStatus.CLOSED_WITHOUT_FORM: CycleEventKind.TASK_CLOSED_WITHOUT_FORM,
    ManualStatus.NOT_APPLICABLE: CycleEventKind.TASK_NOT_APPLICABLE,
    "": CycleEventKind.TASK_RESET,
}
STATUS_EVENTS = {
    CycleStatus.ACTIVE: CycleEventKind.REOPENED,
    CycleStatus.SUSPENDED: CycleEventKind.SUSPENDED,
    CycleStatus.CLOSED: CycleEventKind.CLOSED,
}


def community_level_id(config: ProgrammeConfig | None = None) -> int | None:
    config = config or ProgrammeConfig.get()
    return config.cdd_community_level_id or config.village_level_id


def is_community(unit, config: ProgrammeConfig | None = None) -> bool:
    """CDD-9: whether ``unit`` can go through a cycle."""
    level_id = community_level_id(config)
    if level_id:
        return unit.level_id == level_id
    return not unit.children.exists()


def communities_under(area, config: ProgrammeConfig | None = None):
    """The units inside ``area`` (a commune, a region) that can go through a cycle (CDD-9)."""
    ids = AdministrativeUnit.get_descendant_ids([area.pk])
    units = AdministrativeUnit.objects.filter(pk__in=ids)
    level_id = community_level_id(config)
    if level_id:
        return units.filter(level_id=level_id)
    return units.filter(children__isnull=True)


def ancestor_ids(unit) -> set[int]:
    """``unit`` and every unit above it."""
    ids, node = set(), unit
    while node is not None and node.pk not in ids:
        ids.add(node.pk)
        node = node.parent
    return ids


def attached_facilitators(community):
    """CDD-11: the active FT and FC attached to the community or to a unit above it. Accounts with
    no unit count by their commune (visibility.own_units does the same)."""
    above = ancestor_ids(community)
    by_unit = CustomUser.objects.filter(administrative_units__in=above)
    by_commune = CustomUser.objects.filter(administrative_units__isnull=True, commune_id__in=above)
    return (by_unit | by_commune).filter(role__in=[Role.FT, Role.FC], is_active=True).distinct()


def _has_other_active(community, exclude=None) -> bool:
    others = Cycle.objects.filter(community=community, status=CycleStatus.ACTIVE)
    if exclude is not None:
        others = others.exclude(pk=exclude.pk)
    return others.exists()


@transaction.atomic
def start_cycle(template, community, by=None, facilitators=(), started_on=None, planned_end=None,
                client_uuid=None) -> Cycle:
    """CDD-9."""
    if not is_community(community):
        raise ValidationError({"community": _("A cycle is started for a community (village level).")})
    if _has_other_active(community):
        raise ValidationError({"community": _("This community already has an active cycle.")})
    last = Cycle.objects.select_for_update().filter(community=community).aggregate(n=Max("number"))["n"]
    cycle = Cycle.objects.create(
        template=template, template_version=template.version, community=community, number=(last or 0) + 1,
        started_on=started_on or clock.today(), planned_end=planned_end, created_by=by, client_uuid=client_uuid,
    )
    cycle.facilitators.set(facilitators)
    CycleEvent.objects.create(cycle=cycle, kind=CycleEventKind.STARTED, by=by)
    return cycle


@transaction.atomic
def set_status(cycle: Cycle, status: str, by=None, note: str = "") -> Cycle:
    """CDD-10: suspend, close or reopen (back to active) with a reason."""
    if status == cycle.status:
        return cycle
    if status not in STATUS_EVENTS:
        raise ValidationError({"status": _("Unknown cycle status.")})
    if not note.strip():
        raise ValidationError({"note": _("Give a reason.")})
    if status == CycleStatus.ACTIVE and _has_other_active(cycle.community, exclude=cycle):
        raise ValidationError({"status": _("This community already has an active cycle.")})
    Cycle.objects.filter(pk=cycle.pk).update(status=status, version=F("version") + 1)
    CycleEvent.objects.create(cycle=cycle, kind=STATUS_EVENTS[status], by=by, note=note.strip())
    cycle.refresh_from_db()
    return cycle


@transaction.atomic
def start_cycles(template, communities, by=None, facilitators=(), with_attached=True, started_on=None,
                 planned_end=None) -> tuple[list[Cycle], list[tuple[object, str]]]:
    """CDD-11: start a cycle in each community. Returns the cycles started and, for the communities
    skipped, why (one already has an active cycle, the unit is not a community)."""
    started, skipped = [], []
    for community in communities:
        people = set(facilitators)
        if with_attached:
            people |= set(attached_facilitators(community))
        try:
            with transaction.atomic():
                started.append(start_cycle(template, community, by=by, facilitators=people,
                                           started_on=started_on, planned_end=planned_end))
        except ValidationError as error:
            skipped.append((community, " ".join(error.messages)))
    return started, skipped


def set_facilitators(cycle: Cycle, facilitators) -> Cycle:
    """Who follows the cycle in the field. Bumps the version so the app fetches it again."""
    cycle.facilitators.set(facilitators)
    Cycle.objects.filter(pk=cycle.pk).update(version=F("version") + 1)
    cycle.refresh_from_db()
    return cycle


def template_task(cycle: Cycle, key: str) -> Task:
    task = Task.objects.filter(activity__phase__template=cycle.template_id, key=key).first()
    if task is None:
        raise ValidationError({"task": _("This task is not part of the cycle.")})
    return task


@transaction.atomic
def decide_task(cycle: Cycle, key: str, manual_status: str, by=None, note: str = "",
                client_uuid=None) -> TaskProgress:
    """Record a person's decision on a task (CDD-1, CDD-2, CDD-3). An empty status withdraws it."""
    task = template_task(cycle, key)
    if manual_status not in DECISION_EVENTS:
        raise ValidationError({"status": _("Unknown task status.")})
    note = note.strip()
    if manual_status in (ManualStatus.CLOSED_WITHOUT_FORM, ManualStatus.NOT_APPLICABLE) and not note:
        raise ValidationError({"note": _("Give a reason.")})
    if manual_status == ManualStatus.DONE and task.forms.filter(required=True).exists():
        raise ValidationError({"status": _("This task is done when its forms are submitted.")})
    progress, created = TaskProgress.objects.select_for_update().get_or_create(
        cycle=cycle, task_key=key, defaults={"client_uuid": client_uuid}
    )
    if not created:
        progress.version += 1
    progress.manual_status = manual_status
    progress.note = note
    progress.decided_by = by
    progress.decided_at = clock.now()
    progress.save()
    CycleEvent.objects.create(cycle=cycle, kind=DECISION_EVENTS[manual_status], task_key=key, by=by, note=note)
    return progress
