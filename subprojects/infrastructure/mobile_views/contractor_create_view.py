from django.views.generic.edit import CreateView
from django.urls import reverse_lazy

from src.permissions import IsFieldAgentUserMixin
from subprojects.models import Contractor
from subprojects.infrastructure.forms.contractor_create_form import ContractorMobileCreateForm


class ContractorCreateView(IsFieldAgentUserMixin, CreateView):
    template_name = 'subprojects/mobile/register_contractor.html'
    model = Contractor
    form_class = ContractorMobileCreateForm
    success_url = reverse_lazy('subprojects:mobile:index')
    groups_required = ['Technical facilitator']
