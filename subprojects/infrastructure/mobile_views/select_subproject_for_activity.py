from django.views.generic import TemplateView
from src.permissions import IsFieldAgentUserMixin


class SelectSubprojectForActivityView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'subprojects/mobile/select_subproject_for_activity.html'

    def get_context_data(self, **kwargs):
        kwargs.update({'administrative_units': self.get_descendants(self.request.user.administrative_unit)})
        return super().get_context_data(**kwargs)

    def get_descendants(self, administrative_unit):
        descendants = list()

        def recurse(node):
            if node.children.exists():
                for child in node.children.all():
                    recurse(child)
            else:
                descendants.append(node)

        recurse(administrative_unit)
        return descendants
