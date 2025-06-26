from django.views import generic
from django.contrib import messages
from django.utils.translation import gettext as _
from django.urls import reverse_lazy

from subprojects.models import Contractor
from subprojects.infrastructure.forms.contractor_create_form import ContractorCreateForm


class ContractorListView(generic.edit.FormMixin, generic.ListView):
    model = Contractor
    context_object_name = 'contractors'
    form_class = ContractorCreateForm
    success_url = reverse_lazy('subprojects:contractor_list')

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
        messages.success(self.request, _('Your contractor was successfully assign to the subproject.'))
        return super().form_valid(form)
