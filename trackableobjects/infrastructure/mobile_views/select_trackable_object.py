from django.views.generic import TemplateView
from src.permissions import IsFieldAgentUserMixin
from trackableobjects import visibility
from trackableobjects.models import TrackableObjectInstance


class SelectSubprojectCustomFieldView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'subprojects/mobile/register_menu.html'

    def get_context_data(self, **kwargs):
        trackable_objects = visibility.listed_trackable_objects(self.request.user)
        kwargs.update({'trackable_objects': trackable_objects})

        for trackable_object in kwargs['trackable_objects']:
            if not TrackableObjectInstance.objects.filter(
                trackable_object__id=trackable_object.id
            ).exists():
                trackable_object.has_no_response = True
            else:
                trackable_object.has_no_response = False

        return super().get_context_data(**kwargs)
