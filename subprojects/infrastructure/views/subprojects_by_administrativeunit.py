from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from subprojects.models import Subproject


class AdministrativeUnitSubprojectsView(LoginRequiredMixin, ListView):
    model = Subproject
    template_name = 'administrative_levels/administrative_unit_children.html'
    context_object_name = 'subprojects'
    login_url = '/login/'
    id_list = None

    def get_queryset(self):
        user_unit = self.request.user.administrative_unit

        queryset = self.model._default_manager.filter(
            administrative_level__id__in=self.get_children_ids(user_unit)
        )

        ordering = self.get_ordering()
        if ordering:
            if isinstance(ordering, str):
                ordering = (ordering,)
            queryset = queryset.order_by(*ordering)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Subprojects of {self.request.user.administrative_unit.name}" if self.request.user.administrative_unit else "No Assigned Unit"
        return context

    def get_children_ids(self, administrative_unit):
        def _get_children_ids(au):
            for child in au.children.all():
                _get_children_ids(child)
            self.id_list.append(au.id)

        self.id_list = list()
        _get_children_ids(administrative_unit)
        return self.id_list
