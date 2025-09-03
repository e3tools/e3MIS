from django.views.generic import ListView
from trackableobjects.models import FollowUpEvent, TrackableObject


class FollowUpEventListView(ListView):
    template_name = 'trackable_objects/follow_up_event_list.html'
    model = FollowUpEvent

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        context['trackable_objects'] = TrackableObject.objects.all()
        return context
