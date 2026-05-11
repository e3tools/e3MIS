from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy as _
from trackableobjects.models import FollowUpEvent, TrackableObject


class FollowUpEventListView(LoginRequiredMixin, ListView):
    template_name = 'trackable_objects/follow_up_event_list.html'
    model = FollowUpEvent
    ordering = ['order', 'name']
    extra_context = {
        'title': _('Follow Up Events'),
    }

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        context['trackable_objects'] = TrackableObject.objects.all()
        return context
