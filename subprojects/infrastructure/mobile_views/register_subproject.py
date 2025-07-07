from django.views.generic.edit import CreateView
from django.urls import reverse_lazy

from django.http import HttpResponseRedirect

from subprojects.infrastructure.forms.subproject_field_agent_create_form import SubprojectFieldAgentCreateForm
from subprojects.models import Subproject


class RegisterSubprojectView(CreateView):
    template_name = 'subprojects/mobile/register_subproject.html'
    model = Subproject
    form_class = SubprojectFieldAgentCreateForm
    success_url = reverse_lazy('subprojects:mobile:index')

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        print('form valid')
        self.object = form.save()
        print('----')
        print(self.object)
        print('----')
        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

