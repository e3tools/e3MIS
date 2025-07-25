from django.views.generic import TemplateView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from src.permissions import IsStaffMemberMixin
from subprojects.models import Subproject


class DashboardView(LoginRequiredMixin, IsStaffMemberMixin, TemplateView):
    template_name = 'subprojects/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'access_token': settings.MAPBOX_ACCESS_TOKEN,
            'subprojects': list(Subproject.objects.all().values(
                'external_id', 'name', 'description', 'status',
                'start_date', 'end_date', 'latitude', 'longitude'
            ))
        })
        return context
