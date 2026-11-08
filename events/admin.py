from django.contrib import admin

from events.models import Attendance, Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "start_date", "end_date", "status")


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("event", "day", "number", "full_name", "organisation")
    list_filter = ("event", "day")
    exclude = ("signature",)
