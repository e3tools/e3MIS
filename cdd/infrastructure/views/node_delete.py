from django.contrib import messages
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views import View

from cdd import designer
from cdd.infrastructure.views.mixins import CddStaffMixin
from cdd.models import Activity, Phase, Task, TaskProgress
from trackableobjects.models import FollowUpEventResponse, TrackableObjectInstance


class NodeDeleteView(CddStaffMixin, View):
    """Delete a phase, an activity or a task (and what is under it), after a confirmation page that
    says how many answers and decisions point at the tasks removed. Answers are kept: they keep
    their cycle and task key."""

    MODELS = {"phase": Phase, "activity": Activity, "task": Task}

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        if kwargs["kind"] not in self.MODELS:
            raise Http404
        self.node = get_object_or_404(self.MODELS[kwargs["kind"]], pk=kwargs["pk"])
        self.template = self.node.template
        scope = {"phase": "activity__phase", "activity": "activity", "task": "pk"}[kwargs["kind"]]
        tasks = Task.objects.filter(**{scope: self.node.pk})
        self.task_names = list(tasks.values_list("name", flat=True))
        keys = list(tasks.values_list("key", flat=True))
        tagged = Q(cdd_cycle__template=self.template, cdd_task_key__in=keys)
        self.answer_count = (TrackableObjectInstance.objects.filter(tagged).count()
                             + FollowUpEventResponse.objects.filter(tagged).count())
        self.decision_count = TaskProgress.objects.filter(cycle__template=self.template, task_key__in=keys).count()

    def get(self, request, *args, **kwargs):
        return render(request, "cdd/node_delete.html", {
            "node": self.node, "template": self.template, "task_names": self.task_names,
            "answer_count": self.answer_count, "decision_count": self.decision_count,
            "title": _("Delete %(name)s") % {"name": self.node.name},
        })

    def post(self, request, *args, **kwargs):
        self.node.delete()
        designer.changed(self.template)
        messages.success(request, _("Deleted."))
        return redirect("cdd:template_detail", self.template.pk)
