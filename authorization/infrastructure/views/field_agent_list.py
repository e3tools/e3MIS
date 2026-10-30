from django.views.generic import ListView
from django.views.generic.edit import FormMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.contrib import messages
from django.utils.translation import gettext as _
from django.urls import reverse_lazy

from src.permissions import IsStaffMemberMixin
from administrativelevels.models import AdministrativeUnit, AdministrativeLevel
from authorization.models import CustomUser, GroupRole, Role
from authorization.infrastructure.forms.create_field_agent_form import CreateFieldAgentForm
from fieldmonitoring.core.geography import levels_configured
from fieldmonitoring.core.models import ProgrammeConfig


class FieldAgentListView(LoginRequiredMixin, IsStaffMemberMixin, FormMixin, ListView):
    template_name = 'auth/field_agent_list.html'
    queryset = CustomUser.objects.filter(is_field_agent=True).select_related('supervisor', 'commune', 'region')
    form_class = CreateFieldAgentForm
    success_url = reverse_lazy('authorization:field_agent_list')

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests: instantiate a form instance with the passed
        POST variables and then check if it's valid.
        """
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def put(self, *args, **kwargs):
        return self.post(*args, **kwargs)

    def get_context_data(self, **kwargs):
        levels = AdministrativeLevel.objects.all().order_by('order')
        kwargs['administrative_levels'] = levels
        kwargs['level_orders'] = [level.order for level in levels]
        # The cascade stops at the level the role is attached to (commune, or region for a
        # regional specialist); unset levels leave it open.
        config = ProgrammeConfig.get()
        kwargs['levels_configured'] = levels_configured()
        kwargs['role_levels'] = {
            role: level.order
            for role, level in [(Role.FT, config.commune_level), (Role.FC, config.commune_level),
                                (Role.SC, config.commune_level), (Role.REGIONAL_SPECIALIST, config.region_level)]
            if level is not None
        }
        kwargs['commune_level_name'] = config.commune_level.name if config.commune_level else _('Commune')
        kwargs['region_level_name'] = config.region_level.name if config.region_level else _('Region')
        # A group's default role fills the role; a role pre-selects its groups.
        group_roles = dict(GroupRole.objects.values_list('group_id', 'role'))
        kwargs['group_roles'] = group_roles
        role_groups = {}
        for group_id, role in group_roles.items():
            role_groups.setdefault(role, []).append(group_id)
        kwargs['role_groups'] = role_groups
        # Lets the page show who the supervisor will be once the commune is picked.
        kwargs['supervisor_communes'] = dict(
            CustomUser.objects.filter(role=Role.SC, is_active=True).values_list('pk', 'commune_id')
        )
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        """If the form is valid, redirect to the supplied URL."""
        form.save()
        messages.success(self.request, _('Your field agent was successfully created or updated.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        self.object_list = self.get_queryset()
        allow_empty = self.get_allow_empty()

        # The page reopens the form with what was posted, including the units picked.
        self.posted_units = AdministrativeUnit.objects.filter(
            pk__in=[pk for pk in self.request.POST.getlist('administrative_units') if pk.isdigit()]
        )

        if not allow_empty:
            # When pagination is enabled and object_list is a queryset,
            # it's better to do a cheap query than to load the unpaginated
            # queryset in memory.
            if self.get_paginate_by(self.object_list) is not None and hasattr(
                self.object_list, "exists"
            ):
                is_empty = not self.object_list.exists()
            else:
                is_empty = not self.object_list
            if is_empty:
                raise Http404(
                    _("Empty list and “%(class_name)s.allow_empty” is False.")
                    % {
                        "class_name": self.__class__.__name__,
                    }
                )
        return self.render_to_response(self.get_context_data(form=form, posted_units=self.posted_units))

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
        }

        if self.request.method in ("POST", "PUT"):
            kwargs.update(
                {
                    "data": self.request.POST,
                    "files": self.request.FILES,
                }
            )

            if 'field_agent' in self.request.POST and self.request.POST['field_agent'] != "":
                kwargs.update({"instance": self.queryset.get(pk=self.request.POST['field_agent'])})
        return kwargs
