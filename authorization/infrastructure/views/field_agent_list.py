from django.views.generic import ListView
from django.views.generic.edit import FormMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.contrib import messages
from django.utils.translation import gettext as _
from django.urls import reverse_lazy

from authorization.models import CustomUser
from authorization.infrastructure.forms.create_field_agent_form import CreateFieldAgentForm


class FieldAngentListView(LoginRequiredMixin, FormMixin, ListView):
    template_name = 'auth/field_agent_list.html'
    queryset = CustomUser.objects.filter(is_field_agent=True)
    form_class = CreateFieldAgentForm
    success_url = reverse_lazy('authorization:field_angent_list')

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

    def form_valid(self, form):
        """If the form is valid, redirect to the supplied URL."""
        form.save()
        messages.success(self.request, _('Your field agent was successfully created or updated.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        self.object_list = self.get_queryset()
        allow_empty = self.get_allow_empty()

        print(form.errors)

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
        return self.render_to_response(self.get_context_data(form=form))

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
