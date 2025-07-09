from django.views.generic import TemplateView
from django.db.models import Q, Exists, OuterRef
from src.permissions import IsFieldAgentUserMixin
from subprojects.models import Subproject, SubprojectCustomField, SubprojectFormResponse


class SelectSubprojectCustomFieldView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'subprojects/mobile/select_subproject_custom_field.html'

    def get_context_data(self, **kwargs):
        subproject = Subproject.objects.filter(id=self.kwargs.get('subproject')).first()
        subproject_custom_fields = SubprojectCustomField.objects.filter(
            Q(dependencies_children__isnull=True) |
            Q(dependencies_children__parent__isnull=False) &
            Exists(
                SubprojectFormResponse.objects.filter(
                    custom_form=OuterRef('dependencies_children__parent'),
                    subproject=subproject
                )
            )
        ).distinct()
        kwargs.update({'subproject_custom_fields': subproject_custom_fields})
        kwargs.update({'subproject': subproject})
        return super().get_context_data(**kwargs)
