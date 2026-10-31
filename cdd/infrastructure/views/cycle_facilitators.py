from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views import View

from cdd import services
from cdd.infrastructure.forms.cycle_forms import CycleFacilitatorsForm
from cdd.infrastructure.views.mixins import CddStaffMixin
from cdd.models import Cycle


class CycleFacilitatorsView(CddStaffMixin, View):
    def post(self, request, pk):
        cycle = get_object_or_404(Cycle, pk=pk)
        form = CycleFacilitatorsForm(request.POST, current=cycle.facilitators.all())
        if form.is_valid():
            services.set_facilitators(cycle, form.cleaned_data["facilitators"])
            messages.success(request, _("Facilitators saved."))
        else:
            messages.error(request, _("Pick facilitators from the list."))
        return redirect("cdd:cycle_detail", pk)
