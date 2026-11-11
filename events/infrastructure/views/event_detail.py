from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import TemplateView

from events.attendance import gender_counts, is_signing_day
from events.infrastructure.forms.event_forms import EventForm, EventPosterForm
from events.models import Event
from src.permissions import IsDjangoAdminMixin


def public_url(request, event):
    """The address behind the QR code (in French; the page offers English)."""
    return request.build_absolute_uri(reverse("events:sign", kwargs={"token": event.token}))


class EventDetailView(LoginRequiredMixin, IsDjangoAdminMixin, TemplateView):
    """One event: open or close its list, edit it, the poster, the files and every signature."""

    template_name = "events/event_detail.html"

    def dispatch(self, request, *args, **kwargs):
        self.event = get_object_or_404(Event, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        event = self.event
        kwargs.setdefault("form", EventForm(instance=event))
        kwargs.setdefault("poster_form", EventPosterForm(initial={"poster_color": event.poster_color}))
        kwargs["title"] = event.title
        kwargs["event"] = event
        kwargs["public_url"] = public_url(self.request, event)
        kwargs["signing_day"] = is_signing_day(event)
        genders = {}
        for day, gender, n in event.attendances.values_list("day", "gender").annotate(n=Count("id")):
            genders.setdefault(day, []).extend([gender] * n)
        kwargs["days"] = [(day, gender_counts(genders.get(day, []))) for day in event.days()]
        kwargs["attendances"] = event.attendances.defer("signature")
        kwargs["other_open"] = Event.objects.filter(status=Event.Status.OPEN).exclude(pk=event.pk).first()
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        event, action = self.event, request.POST.get("action")
        if action == "edit":
            form = EventForm(request.POST, instance=event)
            if not form.is_valid():
                return self.render_to_response(self.get_context_data(form=form))
            form.save()
            messages.success(request, _("Event saved."))
        elif action == "open":
            with transaction.atomic():
                # One list is open at a time.
                closed = Event.objects.filter(status=Event.Status.OPEN).exclude(pk=event.pk).update(
                    status=Event.Status.CLOSED
                )
                event.status = Event.Status.OPEN
                event.save(update_fields=["status"])
            messages.success(request, _("The attendance list is open."))
            if closed:
                messages.info(request, _("The event that was open before is now closed."))
        elif action == "close":
            event.status = Event.Status.CLOSED
            event.save(update_fields=["status"])
            messages.success(request, _("The attendance list is closed: the public page no longer accepts "
                                        "signatures."))
        elif action == "poster":
            form = EventPosterForm(request.POST, request.FILES)
            if not form.is_valid():
                return self.render_to_response(self.get_context_data(poster_form=form))
            event.poster_color = form.cleaned_data["poster_color"]
            if form.cleaned_data["banner"]:
                event.banner, event.banner_type = form.cleaned_data["banner"]
            elif form.cleaned_data["remove_banner"]:
                event.banner, event.banner_type = None, ""
            event.save(update_fields=["poster_color", "banner", "banner_type"])
            messages.success(request, _("Poster saved."))
        return redirect("events:detail", pk=event.pk)
