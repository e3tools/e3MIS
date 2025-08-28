from django.views.generic.detail import DetailView
from trackableobjects.models import TrackableObject

from src.permissions import IsFieldAgentUserMixin


class MobileViewsTrackableObjectInstanceListView(IsFieldAgentUserMixin, DetailView):
    template_name = 'trackable_objects/mobile/select_trackable_object_instance.html'
    queryset = TrackableObject.objects.all()
