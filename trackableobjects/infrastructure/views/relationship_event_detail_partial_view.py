from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.views.generic import DetailView

from src.permissions import IsStaffMemberMixin
from trackableobjects.infrastructure.views.relationship_helpers import build_dependency_map
from trackableobjects.models import FollowUpEvent


class RelationshipEventDetailPartialView(LoginRequiredMixin, IsStaffMemberMixin, DetailView):
    """
    HTMX partial: renders a single Follow-up Event's linked Trackable Objects (with
    their IDs) plus its own dependency chain, for the detail panel on the relationship
    overview page. Loaded on demand so the overview page never renders every
    relationship up front.
    """
    model = FollowUpEvent
    template_name = 'trackable_objects/partials/relationship_event_detail.html'
    context_object_name = 'follow_up_event'

    def get_queryset(self):
        return FollowUpEvent.objects.annotate(
            response_count=Count('responses', distinct=True),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        dependency_map = build_dependency_map()
        context['depends_on_names'] = dependency_map.get(self.object.pk, [])
        context['trackable_objects'] = (
            self.object.trackable_objects
            .annotate(instance_count=Count('instances', distinct=True))
            .order_by('name')
        )
        return context
