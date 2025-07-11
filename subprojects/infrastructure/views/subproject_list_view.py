from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from src.permissions import IsStaffMemberMixin
from subprojects.models import Subproject


class SubprojectListView(LoginRequiredMixin, IsStaffMemberMixin, ListView):
    model = Subproject
    template_name = 'subprojects/list.html'
    paginate_by = 100
