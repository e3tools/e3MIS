from django.views.generic.edit import DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy

from src.permissions import IsStaffMemberMixin
from authorization.models import CustomUser


class FieldAgentDeleteView(LoginRequiredMixin, IsStaffMemberMixin, DeleteView):
    model = CustomUser
    success_url = reverse_lazy('authorization:field_agent_list')

    def get_queryset(self):
        return CustomUser.objects.filter(is_field_agent=True)
