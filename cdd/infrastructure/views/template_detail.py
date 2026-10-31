from django.db.models import Prefetch
from django.views.generic import DetailView

from cdd import designer
from cdd.infrastructure.views.mixins import CddStaffMixin
from cdd.models import Activity, CycleTemplate, Phase, Task


class CycleTemplateDetailView(CddStaffMixin, DetailView):
    """The designer: the template's tree, drag to reorder, warnings on forms (CDD-15)."""

    model = CycleTemplate
    template_name = "cdd/template_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tasks = Task.objects.prefetch_related(
            "depends_on", "forms__trackable_object__groups", "forms__follow_up_event__groups"
        )
        context["phases"] = Phase.objects.filter(template=self.object).prefetch_related(
            Prefetch("activities", queryset=Activity.objects.prefetch_related(Prefetch("tasks", queryset=tasks)))
        )
        context["warnings"] = designer.form_warnings(self.object)
        context["keys_locked"] = designer.keys_locked(self.object)
        context["title"] = self.object.name
        return context
