from django.views.generic import TemplateView
from django.db.models import Subquery
from subprojects.models import Subproject, SubprojectCustomField, SubprojectFormResponse


class SelectSubprojectCustomFieldView(TemplateView):
    template_name = 'subprojects/mobile/select_subproject_custom_field.html'

    def get_context_data(self, **kwargs):
        subproject = Subproject.objects.filter(id=self.kwargs.get('subproject')).first()
        subproject_custom_field_ids = SubprojectFormResponse.objects.filter(
            subproject=subproject).values('custom_form__id')
        kwargs.update({'subproject_custom_fields': SubprojectCustomField.objects.exclude(
            id__in=Subquery(subproject_custom_field_ids))})
        kwargs.update({'subproject': subproject})
        print('---')
        print(kwargs)
        print('---')
        return super().get_context_data(**kwargs)
