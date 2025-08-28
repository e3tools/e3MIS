from django.contrib import admin

from .models import (
    TrackableObject,
    FollowUpEvent,
    TrackableObjectInstance,
    FollowUpEventResponse
)


admin.site.register(TrackableObject)
admin.site.register(FollowUpEvent)
admin.site.register(TrackableObjectInstance)
admin.site.register(FollowUpEventResponse)