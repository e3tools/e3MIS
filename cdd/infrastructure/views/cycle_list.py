from django.core.paginator import Paginator
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from administrativelevels.models import AdministrativeUnit
from cdd import progress
from cdd.infrastructure.views.mixins import CddStaffMixin
from cdd.models import Cycle, CycleStatus, CycleTemplate
from fieldmonitoring.core.geography import communes
from fieldmonitoring.core.models import ProgrammeConfig


class CycleListView(CddStaffMixin, TemplateView):
    """Cycles per community, with progress, current phase and warnings (progress.py)."""

    template_name = "cdd/cycle_list.html"
    extra_context = {"title": _("Cycles per community")}
    paginate_by = 50

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        cycles = Cycle.objects.select_related("community__parent", "template").prefetch_related("facilitators")
        commune = AdministrativeUnit.objects.filter(pk=params.get("commune") or None).first()
        if commune:
            cycles = cycles.filter(community_id__in=AdministrativeUnit.get_descendant_ids([commune.pk]))
        if params.get("status") in CycleStatus.values:
            cycles = cycles.filter(status=params["status"])
        if params.get("template", "").isdigit():
            cycles = cycles.filter(template_id=params["template"])
        page = Paginator(cycles.order_by("community__name", "-number"), self.paginate_by).get_page(params.get("page"))
        config = ProgrammeConfig.get()
        rows = []
        for cycle in page:
            state = progress.state(cycle, config=config)
            phase = next((p for p in state.phases if p.id == state.current_phase_id), None)
            rows.append({"cycle": cycle, "state": state, "phase": phase})
        query = params.copy()
        query.pop("page", None)
        context.update({
            "rows": rows, "page_obj": page, "query": query.urlencode(),
            "communes": communes().order_by("name"), "templates": CycleTemplate.objects.all(),
            "statuses": CycleStatus.choices, "selected": params,
        })
        return context
