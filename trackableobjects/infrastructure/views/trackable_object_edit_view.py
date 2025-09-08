import json
from django.views.generic.edit import UpdateView
from django.urls import reverse_lazy
from trackableobjects.models import TrackableObject
from trackableobjects.infrastructure.forms.trackable_object_create_form import TrackableObjectForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from src.permissions import IsStaffMemberMixin


class TrackableObjectEditView(LoginRequiredMixin, IsStaffMemberMixin, UpdateView):
    model = TrackableObject
    form_class = TrackableObjectForm
    template_name = "trackable_objects/create_edit.html"
    success_url = reverse_lazy("trackableobjects:trackable_object_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'custom_forms': self.model.objects.exclude(id=self.object.id)})

        context.update({'groups': Group.objects.all()})
        context.update({'trackable_object_groups': list(self.object.groups.all().values_list(
            'id', flat=True))})

        context['object'].jsonForm = json.dumps(context['object'].jsonForm)
        return context
