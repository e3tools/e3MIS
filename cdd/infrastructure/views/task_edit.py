from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views import View

from cdd import designer
from cdd.infrastructure.forms.designer_forms import TaskEditForm, TaskFormFormSet
from cdd.infrastructure.views.mixins import CddStaffMixin
from cdd.models import Activity, Task


class TaskEditView(CddStaffMixin, View):
    """Add a task to an activity (``activity`` kwarg) or edit one (``pk``), with the forms it needs."""

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        if "pk" in kwargs:
            self.task = get_object_or_404(Task.objects.select_related("activity__phase__template"), pk=kwargs["pk"])
        else:
            activity = get_object_or_404(Activity.objects.select_related("phase__template"), pk=kwargs["activity"])
            last = activity.tasks.order_by("-order").first()
            self.task = Task(activity=activity, order=(last.order + 1) if last else 1)
        self.template = self.task.activity.phase.template

    def render_form(self, form, formset):
        return render(self.request, "cdd/task_form.html", {
            "form": form, "formset": formset, "template": self.template, "task": self.task,
            "title": _("Edit task") if self.task.pk else _("Add task"),
        })

    def get(self, request, *args, **kwargs):
        return self.render_form(
            TaskEditForm(instance=self.task, template=self.template), TaskFormFormSet(instance=self.task)
        )

    def post(self, request, *args, **kwargs):
        form = TaskEditForm(request.POST, instance=self.task, template=self.template)
        formset = TaskFormFormSet(request.POST, instance=self.task)
        if not (form.is_valid() and formset.is_valid()):
            return self.render_form(form, formset)
        with transaction.atomic():
            task = form.save()
            formset.instance = task
            formset.save()
            designer.changed(self.template)
        messages.success(request, _("Saved."))
        return redirect("cdd:template_detail", self.template.pk)
