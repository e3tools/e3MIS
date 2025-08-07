from django.contrib import admin

from .models import (
    TrackableObject,
    FollowUpEvent,
    TrackableObjectResponse,
    FollowUpEventResponse
)


admin.site.register(TrackableObject)
admin.site.register(FollowUpEvent)
admin.site.register(TrackableObjectResponse)
admin.site.register(FollowUpEventResponse)