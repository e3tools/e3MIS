from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin


class AdministrativeLevelsListView(LoginRequiredMixin, TemplateView):
    template_name = 'administrative_levels/list.html'
