from django.views.generic.detail import DetailView
from django.db.models import OuterRef, Exists
from trackableobjects.models import TrackableObject

from src.permissions import IsFieldAgentUserMixin


class MobileViewsTrackableObjectInstanceRegistrationListView(IsFieldAgentUserMixin, DetailView):
    template_name = 'trackable_objects/mobile/select_trackable_object_instance_for_registration.html'
    queryset = TrackableObject.objects.all()

    def get_queryset(self):
        user_group_ids = list(self.request.user.groups.values_list('id', flat=True))

        unmatched_groups = TrackableObject.groups.through.objects.filter(
            trackableobject_id=OuterRef('pk')
        ).exclude(
            group_id__in=user_group_ids
        )

        return TrackableObject.objects.annotate(
            has_unmatched_groups=Exists(unmatched_groups)
        ).filter(
            has_unmatched_groups=False
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_instances'] = self.object.instances.filter(
            created_by=self.request.user
        )
        return context
