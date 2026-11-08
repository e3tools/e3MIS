from django.views.generic import TemplateView

from events.attendance import find
from events.infrastructure.views.public import PublicEventMixin


class EventCheckView(PublicEventMixin, TemplateView):
    """"Have I signed?": by email or phone, the days and numbers of that contact's signatures."""

    template_name = "events/public_check.html"

    def get_context_data(self, **kwargs):
        contact = self.request.GET.get("contact", "").strip()[:200]
        if contact:
            kwargs["contact"] = contact
            kwargs["found"] = find(self.event, contact)
        return super().get_context_data(**kwargs)
