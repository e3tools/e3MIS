from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

from src.permissions import IsStaffMemberMixin
from trackableobjects.models import TrackableObject, FollowUpEvent
from utils.submission_table import build_submission_table
from utils.submission_export import build_export_table, export_response

VALID_FORMATS = ('csv', 'xlsx')


def _created_by(submission):
    user = submission.created_by
    if not user:
        return ''
    return user.get_full_name() or user.email


def _timestamp(value):
    return value.strftime('%Y-%m-%d %H:%M') if value else ''


class TrackableObjectInstancesExportView(LoginRequiredMixin, IsStaffMemberMixin, View):
    """Download a trackable object's form submissions as CSV / XLSX."""

    def get(self, request, pk, fmt):
        if fmt not in VALID_FORMATS:
            raise Http404(_('Unsupported export format.'))

        trackable_object = get_object_or_404(TrackableObject, pk=pk)
        instances = trackable_object.instances.select_related('created_by').prefetch_related('groups', 'attachments')
        schema_fields, rows = build_submission_table(trackable_object.jsonForm, instances, as_text=True)

        leading = [
            (_('ID'), lambda obj: obj.id),
            (_('Created by'), _created_by),
            (_('User group'), lambda obj: ', '.join(group.name for group in obj.groups.all())),
        ]
        trailing = [
            (_('Created'), lambda obj: _timestamp(obj.created_at)),
            (_('Updated'), lambda obj: _timestamp(obj.updated_at)),
        ]
        header, data = build_export_table(schema_fields, rows, leading, trailing)

        filename = '{}-submissions'.format(slugify(trackable_object.name) or 'trackable-object')
        return export_response(fmt, filename, header, data, sheet_title='Submissions')


class FollowUpEventResponsesExportView(LoginRequiredMixin, IsStaffMemberMixin, View):
    """Download a follow-up event's responses as CSV / XLSX."""

    def get(self, request, pk, fmt):
        if fmt not in VALID_FORMATS:
            raise Http404(_('Unsupported export format.'))

        event = get_object_or_404(FollowUpEvent, pk=pk)
        responses = event.responses.select_related('created_by').prefetch_related('attachments')
        schema_fields, rows = build_submission_table(event.jsonForm, responses, as_text=True)

        # Event-level values, constant across rows (mirrors the detail table).
        event_groups = ', '.join(group.name for group in event.groups.all())
        depends_on = ', '.join(
            dep.parent.name for dep in event.dependencies_children.select_related('parent')
        )

        leading = [
            (_('ID'), lambda obj: obj.id),
            (_('Created by'), _created_by),
            (_('User group'), lambda obj: event_groups),
            (_('Depends on'), lambda obj: depends_on),
        ]
        trailing = [
            (_('Created'), lambda obj: _timestamp(obj.created_at)),
            (_('Updated'), lambda obj: _timestamp(obj.updated_at)),
        ]
        header, data = build_export_table(schema_fields, rows, leading, trailing)

        filename = '{}-responses'.format(slugify(event.name) or 'follow-up-event')
        return export_response(fmt, filename, header, data, sheet_title='Responses')
