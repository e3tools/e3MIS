from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View

from events.models import Attendance
from src.permissions import IsDjangoAdminMixin


class AttendanceSignatureView(LoginRequiredMixin, IsDjangoAdminMixin, View):
    """A signature image, for the staff page only: signatures are never public."""

    def get(self, request, pk):
        attendance = get_object_or_404(Attendance, pk=pk)
        response = HttpResponse(bytes(attendance.signature), content_type="image/png")
        response["Cache-Control"] = "private, max-age=3600"
        return response
