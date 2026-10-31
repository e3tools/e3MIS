from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404

from fieldmonitoring.core.models import ProgrammeConfig
from src.permissions import IsStaffMemberMixin


class CddStaffMixin(LoginRequiredMixin, IsStaffMemberMixin):
    """MIS staff, and only while the module is switched on (ProgrammeConfig.cdd_enabled)."""

    def dispatch(self, request, *args, **kwargs):
        if not ProgrammeConfig.get().cdd_enabled:
            raise Http404
        return super().dispatch(request, *args, **kwargs)
