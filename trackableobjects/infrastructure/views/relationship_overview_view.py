from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.db.models import Count
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from src.permissions import IsStaffMemberMixin
from trackableobjects.infrastructure.views.relationship_helpers import build_dependency_map
from trackableobjects.models import FollowUpEvent, FollowUpEventTrackableObject, TrackableObject


class RelationshipOverviewView(LoginRequiredMixin, IsStaffMemberMixin, TemplateView):
    """
    Scalable, read-only overview of how Trackable Objects and Follow-up Events relate.

    Rendered as two compact, paginated/searchable tables (one row per entity, with its
    database ID) rather than one card per trackable object — the earlier design didn't
    scale past a handful of records. Detail (which specific IDs are linked) is loaded
    on demand via HTMX when a row is clicked, so hundreds of entities stay cheap to render.
    """
    template_name = 'trackable_objects/relationship_overview.html'
    extra_context = {'title': _('Relationships')}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        dependency_map = build_dependency_map()

        trackable_objects = (
            TrackableObject.objects
            .annotate(
                event_count=Count('follow_up_events', distinct=True),
                instance_count=Count('instances', distinct=True),
            )
            .prefetch_related('groups')
            .order_by('name')
        )

        follow_up_events = (
            FollowUpEvent.objects
            .annotate(
                object_count=Count('trackable_objects', distinct=True),
                response_count=Count('responses', distinct=True),
            )
            .prefetch_related('groups')
            .order_by('order', 'name')
        )

        # Force evaluation once here (both querysets are only iterated once more, by the
        # template) and attach "depends on" names directly onto each event instance:
        # Django templates can't do a variable-keyed dict lookup (e.g. dependency_map.event.id).
        trackable_objects = list(trackable_objects)
        follow_up_events = list(follow_up_events)
        for event in follow_up_events:
            event.depends_on_names = dependency_map.get(event.pk, [])

        standalone_count = sum(1 for event in follow_up_events if event.object_count == 0)

        stats = {
            'trackable_object_count': len(trackable_objects),
            'follow_up_event_count': len(follow_up_events),
            'link_count': FollowUpEventTrackableObject.objects.count(),
            'standalone_count': standalone_count,
        }

        context.update({
            'trackable_objects': trackable_objects,
            'follow_up_events': follow_up_events,
            'groups': Group.objects.order_by('name'),
            'stats': stats,
        })
        return context
