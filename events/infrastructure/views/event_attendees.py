from django.views.generic import TemplateView

from events import attendance
from events.infrastructure.views.public import PublicEventMixin


class EventAttendeesView(PublicEventMixin, TemplateView):
    """Who has signed, for anyone with the QR code: the number, a shortened name and the
    organisation only (never the email, phone or signature), and the day's total. No download."""

    template_name = "events/public_attendees.html"

    def get_context_data(self, **kwargs):
        days = [day for day in self.event.days() if day <= attendance.today()] or self.event.days()[:1]
        requested = self.request.GET.get("day")
        day = next((d for d in days if d.isoformat() == requested), days[-1])
        kwargs["days"], kwargs["day"] = days, day
        kwargs["rows"] = [
            (a.number, attendance.public_name(a.full_name), a.organisation)
            for a in self.event.attendances.filter(day=day).only("number", "full_name", "organisation")
        ]
        return super().get_context_data(**kwargs)
