from django.urls import path
from trackableobjects.api import views

app_name = 'api'
urlpatterns = [
    path('trackable-object-instance', views.TrackableObjectInstanceRetrieveAPIView.as_view(),
         name='trackable_object_instance'),
    path('follow-up-event/reorder', views.FollowUpEventReorderAPIView.as_view(),
         name='follow_up_event_reorder'),
]
