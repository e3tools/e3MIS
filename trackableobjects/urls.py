from django.urls import path, include

from trackableobjects.infrastructure.views.trackable_object_list_view import TrackableObjectListView
from trackableobjects.infrastructure.views.trackable_object_create_view import TrackableObjectCreateView
from trackableobjects.infrastructure.views.trackable_object_edit_view import TrackableObjectEditView
from trackableobjects.infrastructure.views.trackable_object_detail_view import TrackableObjectDetailView


app_name = 'trackableobjects'
urlpatterns = [
    path('', TrackableObjectListView.as_view(), name='trackable_object_list'),
    path('create/', TrackableObjectCreateView.as_view(), name='trackable_object_create'),
    path('<int:pk>/', TrackableObjectDetailView.as_view(), name='trackable_object_detail'),
    path('<int:pk>/edit/', TrackableObjectEditView.as_view(), name='trackable_object_edit'),
]
