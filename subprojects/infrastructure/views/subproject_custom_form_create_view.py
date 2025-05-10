# subprojects/views.py
from django.views.generic.edit import CreateView, UpdateView
from django.urls import reverse_lazy
from subprojects.models import SubprojectCustomField
from subprojects.infrastructure.forms.subproject_custom_form import SubprojectCustomFieldsForm


class SubprojectCustomFieldsCreateView(CreateView):
    model = SubprojectCustomField
    form_class = SubprojectCustomFieldsForm
    template_name = "subprojects/schema_form.html"
    success_url = reverse_lazy("custom_form_list")

    def post(self, request, *args, **kwargs):
        print(request.POST)
        form = self.get_form()
        if form.is_valid():
            print('here now')
            return self.form_valid(form)
        else:
            print('invalid form')
            return self.form_invalid(form)

    def form_valid(self, form):
        print("SubprojectCustomFieldsCreateView.form_valid")
        # Any extra processing here
        return super().form_valid(form)