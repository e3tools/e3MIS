from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.views.generic import TemplateView

from events.infrastructure.forms.event_forms import EventForm
from events.models import Event
from src.permissions import IsDjangoAdminMixin


class EventListView(LoginRequiredMixin, IsDjangoAdminMixin, TemplateView):
    """Events with their attendance lists, and the form to create one."""

    template_name = "events/event_list.html"

    def get_context_data(self, **kwargs):
        kwargs.setdefault("form", EventForm())
        kwargs["title"] = _("Events")
        kwargs["events"] = Event.objects.annotate(signatures=Count("attendances"))
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        form = EventForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        event = form.save(commit=False)
        event.created_by = request.user
        event.save()
        messages.success(request, _("Event created. Open it when the attendance list should be available."))
        return redirect("events:detail", pk=event.pk)
