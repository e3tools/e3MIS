from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from cdd import progress
from cdd.infrastructure.forms.cycle_forms import CycleFacilitatorsForm, CycleStatusForm
from cdd.infrastructure.views.mixins import CddStaffMixin
from cdd.models import Cycle, CycleStatus
from trackableobjects.models import FollowUpEventResponse, TrackableObjectInstance


class CycleDetailView(CddStaffMixin, TemplateView):
    """One community's cycle: phases, tasks with their status and warnings, forms submitted,
    facilitators, close / suspend / reopen with a reason (CDD-10), and the history."""

    template_name = "cdd/cycle_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cycle = get_object_or_404(
            Cycle.objects.select_related("community", "template", "created_by"), pk=kwargs["pk"]
        )
        state = progress.state(cycle)
        decisions = {p.task_key: p for p in cycle.task_progress.select_related("decided_by")}
        phases = []
        for phase in state.phases:
            tasks = [{"state": t, "decision": decisions.get(t.key)} for t in state.tasks if t.phase_id == phase.id]
            phases.append({"phase": phase, "tasks": tasks})
        answers = [
            *[("record", a) for a in TrackableObjectInstance.objects.filter(cdd_cycle=cycle).select_related(
                "trackable_object", "created_by")],
            *[("event", a) for a in FollowUpEventResponse.objects.filter(cdd_cycle=cycle).select_related(
                "follow_up_event", "created_by")],
        ]
        answers.sort(key=lambda pair: pair[1].created_at, reverse=True)
        names = {t.key: t.name for t in state.tasks}
        status_actions = [(value, label) for value, label in CycleStatus.choices if value != cycle.status]
        context.update({
            "cycle": cycle, "state": state, "phases": phases, "answers": answers, "task_names": names,
            "events": cycle.events.select_related("by")[:100],
            "facilitators_form": CycleFacilitatorsForm(
                initial={"facilitators": list(cycle.facilitators.all())}, current=cycle.facilitators.all()
            ),
            "status_form": CycleStatusForm(), "status_actions": status_actions,
            "title": str(cycle),
        })
        return context
