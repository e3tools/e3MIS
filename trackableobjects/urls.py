from django.urls import path, include

from trackableobjects.infrastructure.views.trackable_object_list_view import TrackableObjectListView
from trackableobjects.infrastructure.views.trackable_object_create_view import TrackableObjectCreateView
from trackableobjects.infrastructure.views.trackable_object_detail_view import TrackableObjectDetailView
from trackableobjects.infrastructure.views.trackable_object_edit_view import TrackableObjectEditView
from trackableobjects.infrastructure.views.response_detail_view import TrackableObjectResponseDetailView
from trackableobjects.infrastructure.mobile_views.select_trackable_object import SelectSubprojectCustomFieldView
from trackableobjects.infrastructure.mobile_views.register_trackable_object_resp import TrackableObjectResponseCreateView
from trackableobjects.infrastructure.mobile_views.follow_up_event_detail import MobileViewsFollowUpEventDetailView
from trackableobjects.infrastructure.mobile_views.register_follow_up_resp import FollowUpEventResponseCreateView
from trackableobjects.infrastructure.views.follow_up_event_create_view import FollowUpEventCreateView
from trackableobjects.infrastructure.views.follow_up_event_detail_view import FollowUpEventDetailView
from trackableobjects.infrastructure.views.follow_up_event_responses_detail_view import FollowUpEventResponseDetailView


app_name = 'trackableobjects'
urlpatterns = [
    path('', TrackableObjectListView.as_view(), name='trackable_object_list'),
    path('create/', TrackableObjectCreateView.as_view(), name='trackable_object_create'),
    path('<int:pk>/', TrackableObjectDetailView.as_view(), name='trackable_object_detail'),
    path('<int:pk>/edit/', TrackableObjectEditView.as_view(), name='trackable_object_edit'),
    path('response/<int:pk>/', TrackableObjectResponseDetailView.as_view(), name='trackable_object_response_detail'),
    path('<int:pk>/follow-up-event/', FollowUpEventDetailView.as_view(), name='follow_up_event_object_detail'),
    path('<int:pk>/follow-up-event/create/', FollowUpEventCreateView.as_view(), name='follow_up_event_object_create'),
    path('follow-up-event/response/<int:pk>/', FollowUpEventResponseDetailView.as_view(), name='follow_up_event_response_detail'),
    path('mobile/', include(([
        path('select-trackable-object/', SelectSubprojectCustomFieldView.as_view(), name='select-trackable-object'),
        path('<int:pk>/edit/', TrackableObjectResponseCreateView.as_view(), name='trackable_object_edit'),
        path('follow-up/<int:pk>/', MobileViewsFollowUpEventDetailView.as_view(), name='follow_up_event_detail'),
        path('follow-up/<int:pk>/form/', FollowUpEventResponseCreateView.as_view(), name='follow_up_event_response_create'),
    ], 'mobile'))),
]
