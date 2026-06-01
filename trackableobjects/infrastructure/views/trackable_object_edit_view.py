import json
from django.views.generic.edit import UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext as _
from trackableobjects.models import TrackableObject, COLOR_TOKENS, COLOR_MAP
from trackableobjects.infrastructure.forms.trackable_object_create_form import TrackableObjectForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from src.permissions import IsStaffMemberMixin
from administrativelevels.models import AdministrativeLevel


class TrackableObjectEditView(LoginRequiredMixin, IsStaffMemberMixin, UpdateView):
    model = TrackableObject
    form_class = TrackableObjectForm
    template_name = "trackable_objects/create_edit.html"
    success_url = reverse_lazy("trackableobjects:trackable_object_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '{} - {}'.format(self.object.name, _('Edit'))
        context.update({'custom_forms': self.model.objects.exclude(id=self.object.id)})
        context.update({'trackable_objects': self.model.objects.all()})
        context.update({'administrative_levels': AdministrativeLevel.objects.all().order_by('order')})

        context.update({'groups': Group.objects.all()})
        context.update({'trackable_object_groups': list(self.object.groups.all().values_list(
            'id', flat=True))})
        context.update({
            'color_tokens': COLOR_TOKENS,
            'color_map': COLOR_MAP,
        })

        context['object'].jsonForm = json.dumps(context['object'].jsonForm)
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Your Trackable Object was successfully created or updated.'))
        return response
