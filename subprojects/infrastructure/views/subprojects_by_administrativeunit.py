from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from administrativelevels.models import AdministrativeUnit


class AdministrativeUnitChildrenView(LoginRequiredMixin, ListView):
    model = AdministrativeUnit
    template_name = 'administrative_levels/administrative_unit_children.html'
    context_object_name = 'children'
    login_url = '/login/'

    def get_queryset(self):
        user_unit = self.request.user.administrative_unit
        if user_unit:
            return AdministrativeUnit.objects.filter(parent=user_unit)
        return AdministrativeUnit.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Children of {self.request.user.administrative_unit.name}" if self.request.user.administrative_unit else "No Assigned Unit"
        return context
