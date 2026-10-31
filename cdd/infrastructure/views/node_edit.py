from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views import View

from cdd import designer
from cdd.infrastructure.forms.designer_forms import ActivityForm, PhaseForm
from cdd.infrastructure.views.mixins import CddStaffMixin
from cdd.models import Activity, CycleTemplate, Phase


class NodeEditView(CddStaffMixin, View):
    """Add or edit a phase (under a template) or an activity (under a phase).

    URL kwargs: ``kind`` ("phase" or "activity") and either ``pk`` (edit) or ``parent`` (add).
    """

    KINDS = {
        "phase": (Phase, PhaseForm, CycleTemplate, "template", gettext_lazy("phase")),
        "activity": (Activity, ActivityForm, Phase, "phase", gettext_lazy("activity")),
    }

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        model, self.form_class, parent_model, self.parent_field, self.label = self.KINDS[kwargs["kind"]]
        if "pk" in kwargs:
            self.node = get_object_or_404(model, pk=kwargs["pk"])
        else:
            parent = get_object_or_404(parent_model, pk=kwargs["parent"])
            last = model.objects.filter(**{self.parent_field: parent}).order_by("-order").first()
            self.node = model(**{self.parent_field: parent, "order": (last.order + 1) if last else 1})
        self.template = self.node.template

    def render_form(self, form):
        verb = _("Edit") if self.node.pk else _("Add")
        return render(self.request, "cdd/node_form.html", {
            "form": form, "template": self.template, "title": f"{verb} {self.label}",
        })

    def get(self, request, *args, **kwargs):
        return self.render_form(self.form_class(instance=self.node))

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST, instance=self.node)
        if not form.is_valid():
            return self.render_form(form)
        form.save()
        designer.changed(self.template)
        messages.success(request, _("Saved."))
        return redirect("cdd:template_detail", self.template.pk)
