from django.views.generic.edit import DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.urls import reverse_lazy

from src.permissions import IsStaffMemberMixin


class GroupDeleteView(LoginRequiredMixin, IsStaffMemberMixin, DeleteView):
    model = Group
    success_url = reverse_lazy('authorization:group_list')
