from django.views.generic import TemplateView
from django.db.models import OuterRef, Exists
from src.permissions import IsFieldAgentUserMixin
from trackableobjects.models import FollowUpEvent, FollowUpEventResponse


class SelectStandaloneFollowUpEventView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'trackable_objects/mobile/select_standalone_follow_up_event.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_group_ids = list(self.request.user.groups.values_list('id', flat=True))

        follow_up_event = FollowUpEvent.objects.get(id=self.kwargs['pk'])
        context['follow_up_event'] = follow_up_event

        # Check group permissions
        unmatched_groups = follow_up_event.groups.all().exclude(id__in=user_group_ids)
        if unmatched_groups.exists():
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

        if follow_up_event.is_one_off:
            # For one-off, check if user already has a response
            response = FollowUpEventResponse.objects.filter(
                follow_up_event=follow_up_event,
                created_by=self.request.user,
                trackable_object_instance__isnull=True,
            ).first()
            context['existing_response'] = response
        else:
            # For repeating, get all user responses
            context['responses'] = FollowUpEventResponse.objects.filter(
                follow_up_event=follow_up_event,
                created_by=self.request.user,
                trackable_object_instance__isnull=True,
            ).order_by('-created_at')

        return context
