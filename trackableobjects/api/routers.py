from rest_framework import routers

from trackableobjects.api import views

router = routers.SimpleRouter()

router.register(r'trackable-object', views.TrackableObjectModelViewSet)
router.register(r'trackable-object-instance', views.TrackableObjectInstanceModelViewSet)
router.register(r'follow-up-event', views.FollowUpEventModelViewSet)
router.register(r'follow-up-event-response', views.FollowUpEventResponseModelViewSet)
router.register(r'follow-up-event-dependency', views.FollowUpEventDependencyModelViewSet)
