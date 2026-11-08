"""Shared by the public pages (no sign-in): the event from the address, and the language links."""
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import translate_url
from django.utils.translation import get_language

from events.models import Event


class PublicEventMixin:
    """The event of the address' token. A draft event does not exist for the public."""

    def dispatch(self, request, *args, **kwargs):
        self.event = get_object_or_404(Event, token=kwargs["token"])
        if self.event.status == Event.Status.DRAFT:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        kwargs["event"] = self.event
        kwargs["title"] = self.event.title
        kwargs["language_links"] = [
            (code, label, translate_url(self.request.get_full_path(), code), code == get_language())
            for code, label in (("fr", "Français"), ("en", "English"))
        ]
        return super().get_context_data(**kwargs)
