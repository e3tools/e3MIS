from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views import View

from cdd import services
from cdd.infrastructure.forms.cycle_forms import CycleStatusForm
from cdd.infrastructure.views.mixins import CddStaffMixin
from cdd.models import Cycle


class CycleStatusView(CddStaffMixin, View):
    """Suspend, close or reopen a cycle with a reason (CDD-10)."""

    def post(self, request, pk):
        cycle = get_object_or_404(Cycle, pk=pk)
        form = CycleStatusForm(request.POST)
        if not form.is_valid():
            messages.error(request, _("Give a reason."))
            return redirect("cdd:cycle_detail", pk)
        try:
            cycle = services.set_status(cycle, form.cleaned_data["status"], by=request.user,
                                        note=form.cleaned_data["note"])
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, _("Cycle status: %s") % cycle.get_status_display())
        return redirect("cdd:cycle_detail", pk)
