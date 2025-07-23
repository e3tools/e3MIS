# subprojects/views.py
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext as _
from subprojects.models import SubprojectCustomField
from subprojects.infrastructure.forms.subproject_custom_form import SubprojectCustomFieldsForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from src.permissions import IsStaffMemberMixin


class SubprojectCustomFieldsCreateView(LoginRequiredMixin, IsStaffMemberMixin, CreateView):
    model = SubprojectCustomField
    form_class = SubprojectCustomFieldsForm
    template_name = "subprojects/schema_form.html"
    success_url = reverse_lazy("subprojects:subproject_custom_fields")

    def get_context_data(self, **kwargs):
        kwargs.update({'custom_forms': self.model.objects.all()})
        kwargs.update({'groups': Group.objects.all()})
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Your Custom Form was successfully created or updated.'))
        return response
