from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import OuterRef, Exists
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy

from subprojects.models import Subproject, SubprojectCustomField, SubprojectFormResponse


class IndexTemplateView(LoginRequiredMixin, TemplateView):
    template_name = 'subprojects/mobile/index.html'

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_field_agent:
            return HttpResponseRedirect(reverse_lazy('subprojects:subproject_list'))
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        user_group_ids = list(self.request.user.groups.values_list('id', flat=True))
        admin_unit_ids = [id for unit in self.request.user.administrative_units.all() for id in self.get_descendants(unit)]

        subprojects_count = Subproject.objects.filter(
            administrative_level__id__in=admin_unit_ids
        ).count()

        unmatched_groups = SubprojectCustomField.groups.through.objects.filter(
            subprojectcustomfield_id=OuterRef('pk')
        ).exclude(
            group_id__in=user_group_ids
        )

        user_custom_fields = SubprojectCustomField.objects.annotate(
            has_unmatched_groups=Exists(unmatched_groups)
        ).filter(
            has_unmatched_groups=False
        )

        custom_fields_count = user_custom_fields.count()
        responses_count = SubprojectFormResponse.objects.filter(
            custom_form__in=user_custom_fields,
            subproject__administrative_level__id__in=admin_unit_ids
        ).count()

        pending_activities = subprojects_count * custom_fields_count - responses_count
        pending_activities = pending_activities if pending_activities > 0 else None
        kwargs.update({'pending_activities': pending_activities})
        return super().get_context_data(**kwargs)

    def get_descendants(self, administrative_unit):
        descendants = list()

        def recurse(node):
            if node.children.exists():
                for child in node.children.all():
                    recurse(child)
            else:
                descendants.append(node.id)

        recurse(administrative_unit)
        return descendants
