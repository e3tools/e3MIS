from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from subprojects.models import Subproject


class SubprojectListView(LoginRequiredMixin, ListView):
    model = Subproject
    template_name = 'subprojects/list.html'
    paginate_by = 100
