from django.urls import path, include

from trackableobjects.infrastructure.views.trackable_object_list_view import TrackableObjectListView
from trackableobjects.infrastructure.views.trackable_object_create_view import TrackableObjectCreateView
from trackableobjects.infrastructure.views.trackable_object_detail_view import TrackableObjectDetailView
from trackableobjects.infrastructure.views.trackable_object_edit_view import TrackableObjectEditView
from trackableobjects.infrastructure.views.response_detail_view import TrackableObjectInstanceDetailView
from trackableobjects.infrastructure.views.follow_up_event_create_view import FollowUpEventCreateView
from trackableobjects.infrastructure.views.follow_up_event_detail_view import FollowUpEventDetailView
from trackableobjects.infrastructure.views.follow_up_event_responses_detail_view import FollowUpEventResponseDetailView
from trackableobjects.infrastructure.views.follow_up_event_list_view import FollowUpEventListView

from trackableobjects.infrastructure.mobile_views.index import IndexTemplateView
from trackableobjects.infrastructure.mobile_views.select_trackable_object import SelectSubprojectCustomFieldView
from trackableobjects.infrastructure.mobile_views.select_trackable_object_for_activity import \
    SelectTrackableObjectForActivityView
from trackableobjects.infrastructure.mobile_views.select_trackable_object_instance_for_registration import \
    MobileViewsTrackableObjectInstanceRegistrationListView
from trackableobjects.infrastructure.mobile_views.register_trackable_object_instance import \
    TrackableObjectInstanceCreateView
from trackableobjects.infrastructure.mobile_views.update_trackable_object_instance import \
    TrackableObjectInstanceUpdateView
from trackableobjects.infrastructure.mobile_views.follow_up_event_detail import MobileViewsFollowUpEventDetailView
from trackableobjects.infrastructure.mobile_views.register_follow_up_resp import FollowUpEventResponseCreateView
from trackableobjects.infrastructure.mobile_views.select_trackable_object_instance_for_activity import \
    MobileViewsTrackableObjectInstanceActivityListView
from trackableobjects.infrastructure.mobile_views.select_follow_up_event import SelectFollowUpEventView

app_name = 'trackableobjects'
urlpatterns = [
    path('', TrackableObjectListView.as_view(), name='trackable_object_list'),
    path('create/', TrackableObjectCreateView.as_view(), name='trackable_object_create'),
    path('<int:pk>/', TrackableObjectDetailView.as_view(), name='trackable_object_detail'),
    path('<int:pk>/edit/', TrackableObjectEditView.as_view(), name='trackable_object_edit'),
    path('response/<int:pk>/', TrackableObjectInstanceDetailView.as_view(), name='trackable_object_instance_detail'),
    path('follow-up-event/', FollowUpEventListView.as_view(), name='follow_up_event_list'),
    path('<int:pk>/follow-up-event/', FollowUpEventDetailView.as_view(), name='follow_up_event_object_detail'),
    path('<int:pk>/follow-up-event/create/', FollowUpEventCreateView.as_view(), name='follow_up_event_object_create'),
    path('follow-up-event/response/<int:pk>/', FollowUpEventResponseDetailView.as_view(),
         name='follow_up_event_response_detail'),
    path('api/', include('trackableobjects.api.urls')),
    path('mobile/', include(([
                                 path('', IndexTemplateView.as_view(), name='index'),
                                 path('select-trackable-object/', SelectSubprojectCustomFieldView.as_view(),
                                      name='select-trackable-object'),
                                 path('select-trackable-object-for-activity/',
                                      SelectTrackableObjectForActivityView.as_view(),
                                      name='select_trackable_object_for_activity'),
                                 path('<int:pk>/', MobileViewsTrackableObjectInstanceRegistrationListView.as_view(),
                                      name='trackable_object_instance_registration_list'),
                                 path('<int:pk>/create/', TrackableObjectInstanceCreateView.as_view(),
                                      name='trackable_object_create'),
                                 path('instance/<int:pk>/edit/', TrackableObjectInstanceUpdateView.as_view(),
                                      name='trackable_object_edit'),
                                 path('<int:pk>/follow-up/',
                                      MobileViewsTrackableObjectInstanceActivityListView.as_view(),
                                      name='trackable_object_instance_activity_list'),
                                 path('instance/<int:pk>/follow-up/list/', SelectFollowUpEventView.as_view(),
                                      name='follow_up_event_list'),
                                 path('instance/<int:trackable_instance>/follow-up/<int:follow_up_event>/',
                                      MobileViewsFollowUpEventDetailView.as_view(),
                                      name='follow_up_event_detail'),
                                 path('instance/<int:trackable_instance>/follow-up/<int:follow_up_event>/form/',
                                      FollowUpEventResponseCreateView.as_view(),
                                      name='follow_up_event_response_create'),
                                 path('follow-up/<int:follow_up_event>/form/response/<int:response>/',
                                      FollowUpEventResponseCreateView.as_view(),
                                      name='follow_up_event_response_update'),
                             ], 'mobile'))),
]
