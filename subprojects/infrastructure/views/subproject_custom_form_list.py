from subprojects.models import SubprojectCustomField
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin

class SubprojectCustomFieldListView(LoginRequiredMixin, ListView):
    model = SubprojectCustomField
    template_name = 'subprojects/custom_field_list.html'
    context_object_name = 'custom_fields'
    paginate_by = 10

    def get_queryset(self):
        return SubprojectCustomField.objects.all()
