from django.views.generic.edit import DeleteView
from django.urls import reverse_lazy

from trackableobjects.models import TrackableObject


class TrackableObjectDeleteView(DeleteView):
    model = TrackableObject
    success_url = reverse_lazy("trackableobjects:trackable_object_list")
