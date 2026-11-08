from django.shortcuts import redirect
from django.views.generic import TemplateView

from events.infrastructure.views.public import PublicEventMixin


class EventThanksView(PublicEventMixin, TemplateView):
    """After signing: the signer's number for the day, or the earlier signature of their contact."""

    template_name = "events/public_thanks.html"

    def get(self, request, *args, **kwargs):
        signed = request.session.get("event_signed")
        attendance = signed and self.event.attendances.filter(pk=signed["id"]).first()
        if not attendance:
            return redirect("events:sign", token=self.event.token)
        return self.render_to_response(self.get_context_data(attendance=attendance, created=signed["created"]))
