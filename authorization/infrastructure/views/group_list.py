from django.views.generic import ListView
from django.views.generic.edit import FormMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.contrib import messages
from django.db.models import Count
from django.utils.translation import gettext as _
from django.urls import reverse_lazy

from src.permissions import IsStaffMemberMixin
from authorization.infrastructure.forms.group_form import GroupForm


class GroupListView(LoginRequiredMixin, IsStaffMemberMixin, FormMixin, ListView):
    template_name = 'auth/group_list.html'
    queryset = Group.objects.annotate(member_count=Count('user')).order_by('name')
    form_class = GroupForm
    success_url = reverse_lazy('authorization:group_list')

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def put(self, *args, **kwargs):
        return self.post(*args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('Group saved successfully.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        self.object_list = self.get_queryset()
        return self.render_to_response(self.get_context_data(form=form))

    def get_form_kwargs(self):
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

            if 'group_id' in self.request.POST and self.request.POST['group_id'] != "":
                kwargs.update({"instance": Group.objects.get(pk=self.request.POST['group_id'])})
        return kwargs
