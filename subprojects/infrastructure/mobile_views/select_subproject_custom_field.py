from django.views.generic import TemplateView
from django.db.models import Q, Exists, OuterRef, Count, Subquery, IntegerField, ExpressionWrapper, F, Value
from src.permissions import IsFieldAgentUserMixin
from subprojects.models import Subproject, SubprojectCustomField, SubprojectFormResponse


class SelectSubprojectCustomFieldView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'subprojects/mobile/select_subproject_custom_field.html'

    def get_context_data(self, **kwargs):
        user_group_ids = list(self.request.user.groups.values_list('id', flat=True))

        matching_group_count = SubprojectCustomField.groups.through.objects.filter(
            subprojectcustomfield_id=OuterRef('pk'),
            group_id__in=user_group_ids
        ).values('subprojectcustomfield_id').annotate(
            count=Count('group_id')
        ).values('count')

        subproject = Subproject.objects.filter(id=self.kwargs.get('subproject')).first()
        subproject_custom_fields = SubprojectCustomField.objects.annotate(
                total_groups=Count('groups', distinct=True),
                matched_groups=Subquery(matching_group_count, output_field=IntegerField()),
            ).filter(
            (
                Q(dependencies_children__isnull=True) |
                Q(dependencies_children__parent__isnull=False) &
                Exists(
                    SubprojectFormResponse.objects.filter(
                        custom_form=OuterRef('dependencies_children__parent'),
                        subproject=subproject
                    )
                )
            ) & (
                Q(total_groups=0) |
                Q(total_groups=F('matched_groups'))
            )
        ).distinct().values('id', 'name')
        kwargs.update({'subproject_custom_fields': subproject_custom_fields})
        kwargs.update({'subproject': subproject})

        for subproject_custom_field in kwargs['subproject_custom_fields']:
            if not SubprojectFormResponse.objects.filter(
                custom_form__id=subproject_custom_field['id'],
                subproject=subproject
            ).exists():
                subproject_custom_field.update({'has_no_response': True})
            else:
                subproject_custom_field.update({'has_no_response': False})

        return super().get_context_data(**kwargs)
