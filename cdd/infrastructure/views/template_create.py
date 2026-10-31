from django.contrib import messages
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.generic import CreateView

from cdd.infrastructure.forms.designer_forms import CycleTemplateForm
from cdd.infrastructure.views.mixins import CddStaffMixin


class CycleTemplateCreateView(CddStaffMixin, CreateView):
    form_class = CycleTemplateForm
    template_name = "cdd/node_form.html"
    extra_context = {"title": gettext_lazy("New cycle")}

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Cycle created. Add its phases."))
        return response

    def get_success_url(self):
        return reverse("cdd:template_detail", args=[self.object.pk])
