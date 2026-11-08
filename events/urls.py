from django.urls import path

from events.infrastructure.views.attendance_signature import AttendanceSignatureView
from events.infrastructure.views.event_attendees import EventAttendeesView
from events.infrastructure.views.event_check import EventCheckView
from events.infrastructure.views.event_detail import EventDetailView
from events.infrastructure.views.event_file import EventFileView
from events.infrastructure.views.event_list import EventListView
from events.infrastructure.views.event_poster import EventPosterView
from events.infrastructure.views.event_sign import EventSignView
from events.infrastructure.views.event_thanks import EventThanksView

app_name = 'events'

urlpatterns = [
    path('events/', EventListView.as_view(), name='list'),
    path('events/<int:pk>/', EventDetailView.as_view(), name='detail'),
    path('events/<int:pk>/poster/', EventPosterView.as_view(), name='poster'),
    path('events/<int:pk>/files/<str:kind>/', EventFileView.as_view(), name='file'),
    path('events/signatures/<int:pk>/', AttendanceSignatureView.as_view(), name='signature'),
    # Public pages (no sign-in), behind the QR code.
    path('e/<str:token>/', EventSignView.as_view(), name='sign'),
    path('e/<str:token>/thanks/', EventThanksView.as_view(), name='thanks'),
    path('e/<str:token>/check/', EventCheckView.as_view(), name='check'),
    path('e/<str:token>/attendees/', EventAttendeesView.as_view(), name='attendees'),
]
