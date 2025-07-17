from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
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
        subprojects_count = Subproject.objects.filter(
            administrative_level__id__in=self.get_descendants(self.request.user.administrative_unit)
        ).count()
        custom_fields_count = SubprojectCustomField.objects.count()
        responses_count = SubprojectFormResponse.objects.count()
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
