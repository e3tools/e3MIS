from django.views.generic import TemplateView
from django.db.models import Q, OuterRef, Count, Subquery, IntegerField, F

from src.permissions import IsFieldAgentUserMixin
from subprojects.models import SubprojectCustomField, SubprojectFormResponse, Subproject


class SelectSubprojectForActivityView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'subprojects/mobile/select_subproject_for_activity.html'
    user_groups = None

    def get_context_data(self, **kwargs):
        self.user_groups = self.request.user.groups.all()
        kwargs.update({'administrative_units': self.get_descendants(self.request.user.administrative_unit)})
        return super().get_context_data(**kwargs)

    def get_descendants(self, administrative_unit):
        descendants = list()
        user_group_ids = list(self.user_groups.values_list('id', flat=True))

        matching_group_count = SubprojectCustomField.groups.through.objects.filter(
            subprojectcustomfield_id=OuterRef('pk'),
            group_id__in=user_group_ids
        ).values('subprojectcustomfield_id').annotate(
            count=Count('group_id')
        ).values('count')

        subproject_custom_field_ids = SubprojectCustomField.objects.annotate(
            total_groups=Count('groups', distinct=True),
            matched_groups=Subquery(matching_group_count, output_field=IntegerField()),
        ).filter(
            Q(total_groups=0) | Q(total_groups=F('matched_groups'))
        ).values('id')

        def recurse(node):
            if node.children.exists():
                for child in node.children.all():
                    recurse(child)
            else:

                subprojects_qs = Subproject.objects.filter(administrative_level=node)

                subprojects_count = 0
                for subproject in subprojects_qs:
                    if len(subproject_custom_field_ids) - SubprojectFormResponse.objects.filter(
                            subproject__id=subproject.id, custom_form__id__in=subproject_custom_field_ids).count() > 0:
                        subprojects_count += 1
                descendants.append({
                    'id': node.id, 'name': node.name,
                    'pending_responses': subprojects_count if subprojects_count > 0 else '',
                })

        recurse(administrative_unit)
        return descendants
