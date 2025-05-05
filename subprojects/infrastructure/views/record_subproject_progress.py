from subprojects.models import Subproject, ProgressUpdate
# View to create a new subproject progress update using htmx
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy

from subprojects.infrastructure.forms.subproject_progress_form import SubprojectProgressForm
from django.template.response import TemplateResponse
from django.contrib import messages

class SubprojectProgressCreateView(CreateView):
    model = ProgressUpdate
    form_class = SubprojectProgressForm
    template_name = "subprojects/partial_progress_form.html"

    def get_initial(self):
        initial = super().get_initial()
        subproject = Subproject.objects.get(pk=self.kwargs['pk'])
        initial['construction_rate'] = subproject.latest_construction_rate
        initial['disbursed_amount'] = subproject.latest_disbursement_rate
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subproject'] = Subproject.objects.get(pk=self.kwargs['pk'])
        return context

    def form_valid(self, form):
        subproject = Subproject.objects.get(pk=self.kwargs['pk'])
        form.instance.subproject = subproject
        subproject.latest_construction_rate = form.instance.construction_rate
        subproject.latest_disbursement_rate = form.instance.disbursed_amount
        subproject.save()
        form.save()
        messages.success(self.request, "Progress update created successfully.")
        return TemplateResponse(self.request, "subprojects/partial_update_success.html", {
            'subproject': subproject,
        })

    def form_invalid(self, form):
        return TemplateResponse(self.request, self.template_name, {
            'form': form,
            'subproject': Subproject.objects.get(pk=self.kwargs['pk']),
        })