from django.views.generic.detail import DetailView
from trackableobjects import visibility
from trackableobjects.models import TrackableObject

from src.permissions import IsFieldAgentUserMixin


class MobileViewsTrackableObjectInstanceRegistrationListView(IsFieldAgentUserMixin, DetailView):
    template_name = 'trackable_objects/mobile/select_trackable_object_instance_for_registration.html'
    queryset = TrackableObject.objects.all()

    def get_queryset(self):
        return visibility.listed_trackable_objects(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_instances'] = self.object.instances.filter(
            created_by=self.request.user
        )
        return context
