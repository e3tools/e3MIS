from django.views.generic.detail import DetailView
from trackableobjects.models import TrackableObject

from src.permissions import IsFieldAgentUserMixin


class MobileViewsTrackableObjectInstanceRegistrationListView(IsFieldAgentUserMixin, DetailView):
    template_name = 'trackable_objects/mobile/select_trackable_object_instance_for_registration.html'
    queryset = TrackableObject.objects.all()
