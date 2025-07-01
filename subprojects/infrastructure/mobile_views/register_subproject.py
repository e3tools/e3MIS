from django.views.generic.edit import CreateView
from django.urls import reverse_lazy

from subprojects.infrastructure.forms.subproject_field_agent_create_form import SubprojectFieldAgentCreateForm
from subprojects.models import Subproject


class RegisterSubprojectView(CreateView):
    template_name = 'subprojects/mobile/register_subproject.html'
    model = Subproject
    form_class = SubprojectFieldAgentCreateForm
    success_url = reverse_lazy('subprojects:mobile:index')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

