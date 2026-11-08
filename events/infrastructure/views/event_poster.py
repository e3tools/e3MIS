from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from events import exports
from events.infrastructure.views.event_detail import public_url
from events.models import Event
from src.permissions import IsDjangoAdminMixin


class EventPosterView(LoginRequiredMixin, IsDjangoAdminMixin, TemplateView):
    """An A4 poster with the QR code, to print from the browser (or save as PDF)."""

    template_name = "events/poster.html"

    def get_context_data(self, **kwargs):
        event = get_object_or_404(Event, pk=self.kwargs["pk"])
        url = public_url(self.request, event)
        kwargs.update(event=event, title=event.title, public_url=url, qr_svg=exports.qr(url).svg_inline(
            scale=10, border=0, omitsize=True))
        return super().get_context_data(**kwargs)
