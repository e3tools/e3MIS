"""Editing a cycle template in the MIS designer.

- CDD-12 Every change to the tree (phases, activities, tasks, their forms, order or dependencies)
         raises the template's version, so the field app fetches it again.
- CDD-13 A task key is fixed once a cycle follows the template: answers and decisions refer to
         tasks by key. New tasks get a key made from their name, unique in the template.
- CDD-14 "Starts after" may not loop back to the task itself.
- CDD-15 The designer warns (never blocks) when a task's form cannot be filled by the people who
         should fill it: an inactive form, a form with no group, or facilitators of active cycles
         who are not in every group of the form (``visibility.can_fill``).
"""
from django.db import transaction
from django.utils.text import slugify
from django.utils.translation import gettext as _

from trackableobjects.visibility import can_fill

from .models import Activity, Cycle, CycleStatus, Phase, Task, TaskForm

KEY_LENGTH = 64


def changed(template):
    """CDD-12."""
    template.bump_version()


def keys_locked(template) -> bool:
    """CDD-13."""
    return Cycle.objects.filter(template=template).exists()


def new_key(template, name: str) -> str:
    """CDD-13: a slug of the name, made unique in the template with -2, -3, …"""
    base = slugify(name)[:KEY_LENGTH - 4] or "tache"
    taken = set(template.tasks().values_list("key", flat=True))
    key, n = base, 2
    while key in taken:
        key, n = f"{base}-{n}", n + 1
    return key


def loops_back(task, depends_on) -> bool:
    """CDD-14: whether making ``task`` depend on ``depends_on`` would close a loop."""
    if task.pk is None:
        return False
    seen, todo = set(), [t.pk for t in depends_on]
    while todo:
        pk = todo.pop()
        if pk == task.pk:
            return True
        if pk in seen:
            continue
        seen.add(pk)
        todo.extend(Task.objects.filter(pk=pk).values_list("depends_on", flat=True).exclude(depends_on=None))
    return False


NODES = {"phase": Phase, "activity": Activity, "task": Task}


@transaction.atomic
def reorder(template, kind: str, ordered_ids: list[int]) -> None:
    """Set ``order`` 1, 2, … on nodes of ``template`` in the order given (CDD-12)."""
    model = NODES[kind]
    scope = {
        "phase": {"template": template},
        "activity": {"phase__template": template},
        "task": {"activity__phase__template": template},
    }[kind]
    nodes = {node.pk: node for node in model.objects.filter(pk__in=ordered_ids, **scope)}
    for order, pk in enumerate(ordered_ids, start=1):
        node = nodes.get(pk)
        if node is not None and node.order != order:
            node.order = order
            node.save(update_fields=["order"])
    changed(template)


def form_warnings(template) -> dict[int, list[str]]:
    """CDD-15: TaskForm id → warnings."""
    facilitators = {
        user.pk: user
        for cycle in Cycle.objects.filter(template=template, status=CycleStatus.ACTIVE).prefetch_related(
            "facilitators__groups"
        )
        for user in cycle.facilitators.all()
    }.values()
    warnings = {}
    task_forms = TaskForm.objects.filter(task__activity__phase__template=template).select_related(
        "trackable_object", "follow_up_event"
    ).prefetch_related("trackable_object__groups", "follow_up_event__groups")
    for task_form in task_forms:
        form = task_form.trackable_object or task_form.follow_up_event
        found = []
        if not getattr(form, "is_active", True):
            found.append(_("The form is not active: agents do not see it."))
        if not form.groups.exists():
            found.append(_("The form has no group: no agent can fill it."))
        else:
            missing = [str(user) for user in facilitators if not can_fill(user, form)]
            if missing:
                found.append(
                    _("Facilitators of active cycles who cannot fill it (not in every group of the form): %s")
                    % ", ".join(sorted(missing))
                )
        if found:
            warnings[task_form.pk] = found
    return warnings
