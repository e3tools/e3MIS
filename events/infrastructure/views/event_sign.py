import time

from django.shortcuts import redirect
from django.utils.translation import get_language
from django.views.generic import TemplateView

from events.attendance import is_signing_day, sign
from events.infrastructure.forms.event_forms import AttendanceForm
from events.infrastructure.views.public import PublicEventMixin

# Signatures one phone may send in an hour (someone may sign for a few others).
SIGNS_PER_HOUR = 20


class EventSignView(PublicEventMixin, TemplateView):
    """The page behind the QR code: the attendance form, open to anyone on the event's days."""

    template_name = "events/public_sign.html"

    def get_context_data(self, **kwargs):
        kwargs.setdefault("form", AttendanceForm())
        kwargs["signing_day"] = is_signing_day(self.event)
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        if not is_signing_day(self.event):
            return redirect("events:sign", token=self.event.token)
        form = AttendanceForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        if form.cleaned_data["website"]:
            return redirect("events:sign", token=self.event.token)
        now = time.time()
        recent = [stamp for stamp in request.session.get("event_signs", []) if now - stamp < 3600]
        if len(recent) >= SIGNS_PER_HOUR:
            return self.render_to_response(self.get_context_data(form=form, too_many=True))
        attendance, created = sign(self.event, form.cleaned_data, form.cleaned_data["signature"], get_language())
        if created:
            request.session["event_signs"] = recent + [now]
        request.session["event_signed"] = {"id": attendance.pk, "created": created}
        return redirect("events:thanks", token=self.event.token)
