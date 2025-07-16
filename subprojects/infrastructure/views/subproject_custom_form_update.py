# subprojects/views.py
import json
from django.views.generic.edit import UpdateView
from django.urls import reverse_lazy
from subprojects.models import SubprojectCustomField
from subprojects.infrastructure.forms.subproject_custom_form import SubprojectCustomFieldsForm
from django.contrib.auth.mixins import LoginRequiredMixin
from src.permissions import IsStaffMemberMixin


class SubprojectCustomFieldsUpdateView(LoginRequiredMixin, IsStaffMemberMixin, UpdateView):
    model = SubprojectCustomField
    form_class = SubprojectCustomFieldsForm
    template_name = "subprojects/schema_form.html"
    success_url = reverse_lazy("subprojects:subproject_custom_fields")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'custom_forms': self.model.objects.exclude(id=self.object.id)})
        context.update({'custom_form_dependencies': list(self.object.dependencies_children.all().values_list(
            'parent__id', flat=True))})
        context['object'].config_schema = json.dumps(context['object'].config_schema)
        return context
