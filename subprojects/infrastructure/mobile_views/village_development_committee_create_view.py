from django.views.generic.edit import CreateView
from django.urls import reverse_lazy

from src.permissions import IsFieldAgentUserMixin
from subprojects.models import VillageDevelopmentCommittee
from subprojects.infrastructure.forms.village_development_committee_create_form import (
    VillageDevelopmentCommitteeCreateForm
)


class VillageDevelopmentCommitteeCreateView(IsFieldAgentUserMixin, CreateView):
    template_name = 'subprojects/mobile/register_village_development_committee.html'
    model = VillageDevelopmentCommittee
    form_class = VillageDevelopmentCommitteeCreateForm
    success_url = reverse_lazy('subprojects:mobile:index')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.user.administrative_unit is not None:
            kwargs.update({"user": self.request.user})
        return kwargs
