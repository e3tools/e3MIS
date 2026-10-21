from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import DeleteView
from django.urls import reverse_lazy

from src.permissions import IsAdminMemberMixin

from trackableobjects.models import TrackableObject


class TrackableObjectDeleteView(LoginRequiredMixin, IsAdminMemberMixin, DeleteView):
    model = TrackableObject
    success_url = reverse_lazy("trackableobjects:trackable_object_list")
