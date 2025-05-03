from django.views.generic.edit import UpdateView
from django.template.response import TemplateResponse
from subprojects.models import Subproject
from subprojects.infrastructure.forms.subproject_update_form import SubprojectForm
from django.contrib import messages

class SubprojectUpdateView(UpdateView):
    model = Subproject
    form_class = SubprojectForm
    template_name = "subprojects/partial_update_form.html"

    def form_valid(self, form):
        form.save()
        return TemplateResponse(self.request, "subprojects/partial_update_success.html", {
            'subproject': self.object,
        })

    def form_invalid(self, form):
        print('here invalid')
        return TemplateResponse(self.request, self.template_name, {
            'form': form,
            'object': self.object,
        })