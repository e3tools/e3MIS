from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views import View

from administrativelevels.models import AdministrativeUnit
from cdd import services
from cdd.infrastructure.forms.cycle_forms import CycleStartForm
from cdd.infrastructure.views.mixins import CddStaffMixin
from cdd.models import Cycle, CycleStatus


def community_rows(commune):
    """The communities of ``commune``: (unit, active cycle or None)."""
    if commune is None:
        return []
    units = services.communities_under(commune).order_by("name")
    active = {c.community_id: c for c in Cycle.objects.filter(community__in=units, status=CycleStatus.ACTIVE)}
    return [(unit, active.get(unit.pk)) for unit in units]


def selected_commune(data):
    pk = data.get("commune")
    return AdministrativeUnit.objects.filter(pk=pk).first() if pk and str(pk).isdigit() else None


class CycleStartView(CddStaffMixin, View):
    """Start cycles for several communities of a commune at once (CDD-9, CDD-11)."""

    def render_form(self, form, commune):
        rows = community_rows(commune)
        return render(self.request, "cdd/cycle_start.html", {
            "form": form, "rows": rows, "commune": commune, "title": _("Start cycles"),
            "chosen": {str(pk) for pk in form["communities"].value() or []},
        })

    def choices(self, commune):
        return [(str(unit.pk), unit.name) for unit, active in community_rows(commune) if active is None]

    def get(self, request):
        commune = selected_commune(request.GET)
        initial = {"commune": commune.pk} if commune else {}
        return self.render_form(CycleStartForm(initial=initial, community_choices=self.choices(commune)), commune)

    def post(self, request):
        commune = selected_commune(request.POST)
        form = CycleStartForm(request.POST, community_choices=self.choices(commune))
        if not form.is_valid():
            return self.render_form(form, commune)
        data = form.cleaned_data
        communities = AdministrativeUnit.objects.filter(pk__in=data["communities"]).order_by("name")
        started, skipped = services.start_cycles(
            data["template"], communities, by=request.user, facilitators=data["facilitators"],
            with_attached=data["with_attached"], started_on=data["started_on"], planned_end=data["planned_end"],
        )
        if started:
            messages.success(request, ngettext("%(n)d cycle started.", "%(n)d cycles started.", len(started))
                             % {"n": len(started)})
        for community, reason in skipped:
            messages.warning(request, f"{community.name}: {reason}")
        no_facilitator = [c.community.name for c in started if not c.facilitators.exists()]
        if no_facilitator:
            messages.warning(request, _("No facilitator assigned yet: %s") % ", ".join(no_facilitator))
        return redirect(f"{reverse('cdd:cycle_list')}?commune={data['commune'].pk}")


class CycleCommunitiesView(CddStaffMixin, View):
    """The community checkboxes of the start page for the commune picked (htmx)."""

    def get(self, request):
        return render(request, "cdd/partials/cycle_communities.html", {
            "rows": community_rows(selected_commune(request.GET)), "chosen": set(),
        })
