from trackableobjects.models import TrackableObject
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from src.permissions import IsStaffMemberMixin


class TrackableObjectListView(LoginRequiredMixin, IsStaffMemberMixin, ListView):
    model = TrackableObject
    template_name = 'trackable_objects/list.html'
    context_object_name = 'trackable_objects'
    paginate_by = 10

    def get_queryset(self):
        return TrackableObject.objects.all()
