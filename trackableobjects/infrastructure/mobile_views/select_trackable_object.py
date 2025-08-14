from django.views.generic import TemplateView
from django.db.models import Q, Exists, OuterRef, Count, Subquery, IntegerField, F
from src.permissions import IsFieldAgentUserMixin
from trackableobjects.models import TrackableObject, TrackableObjectResponse


class SelectSubprojectCustomFieldView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'trackable_objects/mobile/select_trackable_object.html'

    def get_context_data(self, **kwargs):
        user_group_ids = list(self.request.user.groups.values_list('id', flat=True))

        matching_group_count = TrackableObject.groups.through.objects.filter(
            trackableobject_id=OuterRef('pk'),
            group_id__in=user_group_ids
        ).values('trackableobject_id').annotate(
            count=Count('group_id')
        ).values('count')

        trackable_objects = TrackableObject.objects.annotate(
                total_groups=Count('groups', distinct=True),
                matched_groups=Subquery(matching_group_count, output_field=IntegerField()),
            ).filter(
                Q(total_groups=0) |
                Q(total_groups=F('matched_groups'))
        ).distinct().values('id', 'name')
        kwargs.update({'trackable_objects': trackable_objects})

        for trackable_object in kwargs['trackable_objects']:
            if not TrackableObjectResponse.objects.filter(
                trackable_object__id=trackable_object['id']
            ).exists():
                trackable_object.update({'has_no_response': True})
            else:
                trackable_object.update({'has_no_response': False})

        return super().get_context_data(**kwargs)
