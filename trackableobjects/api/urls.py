from django.urls import path
from trackableobjects.api import views

app_name = 'api'
urlpatterns = [
    path('trackable-object-instance', views.TrackableObjectInstanceRetrieveAPIView.as_view(),
         name='trackable_object_instance'),
]
