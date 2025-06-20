from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from authorization.models import CustomUser
from authorization.infrastructure.forms.create_field_agent_form import CreateFieldAgentForm


class FieldAngentListView(LoginRequiredMixin, TemplateView):
    template_name = 'auth/field_agent_list.html'
    form_class = CreateFieldAgentForm

    def get_context_data(self, **kwargs):
        context = kwargs
        context['field_angent_list'] = CustomUser.objects.filter(is_field_agent=True)
        context['field_angent_form'] = self.form_class()
        return super().get_context_data(**context)
