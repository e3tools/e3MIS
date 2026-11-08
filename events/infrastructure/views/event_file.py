from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.views import View

from events import exports
from events.infrastructure.views.event_detail import public_url
from events.models import Event
from src.permissions import IsDjangoAdminMixin

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class EventFileView(LoginRequiredMixin, IsDjangoAdminMixin, View):
    """The files of an event: signed list (PDF, Excel), blank list to print, QR code, logo band."""

    def get(self, request, pk, kind):
        event = get_object_or_404(Event, pk=pk)
        name = slugify(event.title)[:50] or "event"
        if kind == "pdf":
            day = next((d for d in event.days() if d.isoformat() == request.GET.get("day")), None)
            content, content_type = exports.attendance_pdf(event, day), "application/pdf"
            filename = f"{name}_attendance{'_' + day.isoformat() if day else ''}.pdf"
        elif kind == "xlsx":
            content, content_type, filename = exports.attendance_xlsx(event), XLSX, f"{name}_attendance.xlsx"
        elif kind == "blank":
            content, content_type, filename = exports.blank_pdf(event), "application/pdf", f"{name}_blank.pdf"
        elif kind == "qr":
            content, content_type = exports.qr_png(public_url(request, event)), "image/png"
            filename = f"{name}_qr.png"
        elif kind == "banner" and event.banner:
            return HttpResponse(bytes(event.banner), content_type=event.banner_type)
        else:
            raise Http404
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
