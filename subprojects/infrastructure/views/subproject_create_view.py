from django.urls import reverse
from django.views.generic import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from src.permissions import IsStaffMemberMixin
from subprojects.models import Subproject


class SubprojectCreateView(LoginRequiredMixin, IsStaffMemberMixin, CreateView):
    template_name = 'subprojects/create.html'
    model = Subproject
    fields = [
        "name",
        "description",
        "status",
        "start_date",
        "end_date",
        "latitude",
        "longitude",
        "contractors",
        "administrative_level",
        "latest_construction_rate",
        "latest_disbursement_rate",
        "beneficiary_groups"
    ]

    def get_success_url(self):
        return reverse('subprojects:subproject_list')