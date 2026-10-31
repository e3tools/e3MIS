import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from cdd import designer
from cdd.infrastructure.views.mixins import CddStaffMixin
from cdd.models import CycleTemplate


class TreeReorderView(CddStaffMixin, View):
    """Drag and drop in the designer: ``{"kind": "phase"|"activity"|"task", "ordered_ids": [...]}``."""

    def post(self, request, pk):
        template = get_object_or_404(CycleTemplate, pk=pk)
        try:
            body = json.loads(request.body)
            kind, ids = body["kind"], [int(pk) for pk in body["ordered_ids"]]
        except (ValueError, KeyError, TypeError):
            return JsonResponse({"error": "bad_request"}, status=400)
        if kind not in designer.NODES:
            return JsonResponse({"error": "bad_request"}, status=400)
        designer.reorder(template, kind, ids)
        return JsonResponse({"version": template.version})
