from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import UpdateView

from cdd.infrastructure.forms.designer_forms import CycleTemplateForm
from cdd.infrastructure.views.mixins import CddStaffMixin
from cdd.models import CycleTemplate


class CycleTemplateEditView(CddStaffMixin, UpdateView):
    model = CycleTemplate
    form_class = CycleTemplateForm
    template_name = "cdd/node_form.html"
    extra_context = {"title": _("Edit cycle")}

    def get_context_data(self, **kwargs):
        return super().get_context_data(template=self.object, **kwargs)

    def get_success_url(self):
        return reverse("cdd:template_detail", args=[self.object.pk])
