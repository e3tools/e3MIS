from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.views.generic import DetailView

from src.permissions import IsStaffMemberMixin
from trackableobjects.infrastructure.views.relationship_helpers import build_dependency_map
from trackableobjects.models import TrackableObject


class RelationshipObjectDetailPartialView(LoginRequiredMixin, IsStaffMemberMixin, DetailView):
    """
    HTMX partial: renders a single Trackable Object's linked Follow-up Events (with
    their IDs) for the detail panel on the relationship overview page. Loaded on demand
    so the overview page never renders every relationship up front.
    """
    model = TrackableObject
    template_name = 'trackable_objects/partials/relationship_object_detail.html'
    context_object_name = 'trackable_object'

    def get_queryset(self):
        return TrackableObject.objects.annotate(
            instance_count=Count('instances', distinct=True),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        dependency_map = build_dependency_map()
        follow_up_events = list(
            self.object.follow_up_events
            .annotate(response_count=Count('responses', distinct=True))
            .order_by('order', 'name')
        )
        for event in follow_up_events:
            event.depends_on_names = dependency_map.get(event.pk, [])

        context['follow_up_events'] = follow_up_events
        return context
