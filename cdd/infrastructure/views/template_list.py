from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView

from cdd.infrastructure.views.mixins import CddStaffMixin
from cdd.models import CycleStatus, CycleTemplate


class CycleTemplateListView(CddStaffMixin, ListView):
    template_name = "cdd/template_list.html"
    extra_context = {"title": _("CDD cycle designer")}

    def get_queryset(self):
        return CycleTemplate.objects.annotate(
            phase_count=Count("phases", distinct=True),
            active_cycles=Count("cycles", filter=Q(cycles__status=CycleStatus.ACTIVE), distinct=True),
            cycle_count=Count("cycles", distinct=True),
        )
