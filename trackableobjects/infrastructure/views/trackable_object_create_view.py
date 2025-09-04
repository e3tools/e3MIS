from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext as _
from trackableobjects.models import TrackableObject
from trackableobjects.infrastructure.forms.trackable_object_create_form import TrackableObjectForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from src.permissions import IsStaffMemberMixin


class TrackableObjectCreateView(LoginRequiredMixin, IsStaffMemberMixin, CreateView):
    model = TrackableObject
    form_class = TrackableObjectForm
    template_name = "trackable_objects/create_edit.html"
    success_url = reverse_lazy("trackableobjects:trackable_object_list")

    def get_context_data(self, **kwargs):
        kwargs.update({'trackable_objects': self.model.objects.all()})
        kwargs.update({'groups': Group.objects.all()})
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Your Trackable Object was successfully created or updated.'))
        return response

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs
