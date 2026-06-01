from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext as _, gettext_lazy as _l
from trackableobjects.models import TrackableObject, COLOR_TOKENS, COLOR_MAP
from trackableobjects.infrastructure.forms.trackable_object_create_form import TrackableObjectForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from src.permissions import IsStaffMemberMixin
from administrativelevels.models import AdministrativeLevel


class TrackableObjectCreateView(LoginRequiredMixin, IsStaffMemberMixin, CreateView):
    model = TrackableObject
    form_class = TrackableObjectForm
    template_name = "trackable_objects/create_edit.html"
    success_url = reverse_lazy("trackableobjects:trackable_object_list")
    extra_context = {
        'title': _l('Create Trackable Object'),
    }

    def get_context_data(self, **kwargs):
        kwargs.update({
            'trackable_objects': self.model.objects.all(),
            'groups': Group.objects.all(),
            'color_tokens': COLOR_TOKENS,
            'color_map': COLOR_MAP,
            'administrative_levels': AdministrativeLevel.objects.all().order_by('order'),
        })
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Your Trackable Object was successfully created or updated.'))
        return response

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs
