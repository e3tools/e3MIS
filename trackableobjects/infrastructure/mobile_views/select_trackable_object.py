from django.views.generic import TemplateView
from django.db.models import OuterRef, Exists
from src.permissions import IsFieldAgentUserMixin
from trackableobjects.models import TrackableObject, TrackableObjectInstance


class SelectSubprojectCustomFieldView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'subprojects/mobile/register_menu.html'

    def get_context_data(self, **kwargs):
        user_group_ids = list(self.request.user.groups.values_list('id', flat=True))

        matched_groups = TrackableObject.groups.through.objects.filter(
            trackableobject_id=OuterRef('pk'),
            group_id__in=user_group_ids
        )

        trackable_objects = TrackableObject.objects.filter(
            Exists(matched_groups)
        )
        kwargs.update({'trackable_objects': trackable_objects})

        for trackable_object in kwargs['trackable_objects']:
            if not TrackableObjectInstance.objects.filter(
                trackable_object__id=trackable_object.id
            ).exists():
                trackable_object.has_no_response = True
            else:
                trackable_object.has_no_response = False

        return super().get_context_data(**kwargs)
