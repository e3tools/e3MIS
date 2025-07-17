from django.views.generic import TemplateView
from django.db.models import Subquery

from src.permissions import IsFieldAgentUserMixin
from subprojects.models import SubprojectCustomField, SubprojectFormResponse, Subproject


class SelectSubprojectForActivityView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'subprojects/mobile/select_subproject_for_activity.html'

    def get_context_data(self, **kwargs):
        kwargs.update({'administrative_units': self.get_descendants(self.request.user.administrative_unit)})
        return super().get_context_data(**kwargs)

    def get_descendants(self, administrative_unit):
        descendants = list()
        subproject_custom_field_count = SubprojectCustomField.objects.count()

        def recurse(node):
            if node.children.exists():
                for child in node.children.all():
                    recurse(child)
            else:
                subprojects_qs = Subproject.objects.filter(administrative_level=node)
                subprojects_count = 0
                for subproject in subprojects_qs:
                    if subproject_custom_field_count - SubprojectFormResponse.objects.filter(subproject__id=subproject.id).count() > 0:
                        subprojects_count += 1
                descendants.append({
                    'id': node.id, 'name': node.name,
                    'pending_responses': subprojects_count if subprojects_count > 0 else '',
                })

        recurse(administrative_unit)
        return descendants
