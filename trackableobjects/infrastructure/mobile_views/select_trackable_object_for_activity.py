from django.views.generic import TemplateView
from django.db.models import OuterRef, Exists

from src.permissions import IsFieldAgentUserMixin
from subprojects.models import SubprojectCustomField, SubprojectFormResponse, Subproject
from trackableobjects.models import TrackableObject, FollowUpEvent


class SelectTrackableObjectForActivityView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'trackable_objects/mobile/select_trackable_object_for_activity.html'
    user_groups = None

    def get_context_data(self, **kwargs):
        self.user_groups = self.request.user.groups.all()
        self.user_group_ids = list(self.user_groups.values_list('id', flat=True))
        kwargs.update({'administrative_units': [d for unit in self.request.user.administrative_units.all() for d in self.get_descendants(unit)]})

        matched_groups = TrackableObject.groups.through.objects.filter(
            trackableobject_id=OuterRef('pk'),
            group_id__in=self.user_group_ids
        )

        kwargs.update({'trackable_objects': TrackableObject.objects.filter(Exists(matched_groups))})

        # Standalone follow-up events (not related to any trackable object)
        unmatched_fe_groups = FollowUpEvent.groups.through.objects.filter(
            followupevent_id=OuterRef('pk')
        ).exclude(group_id__in=self.user_group_ids)

        kwargs['standalone_follow_up_events'] = FollowUpEvent.objects.filter(
            trackable_objects=None,
            is_active=True,
        ).annotate(
            has_unmatched_groups=Exists(unmatched_fe_groups)
        ).filter(has_unmatched_groups=False)

        return super().get_context_data(**kwargs)

    def get_descendants(self, administrative_unit):
        descendants = list()

        unmatched_groups = SubprojectCustomField.groups.through.objects.filter(
            subprojectcustomfield_id=OuterRef('pk')
        ).exclude(
            group_id__in=self.user_group_ids
        )

        subproject_custom_field_ids = SubprojectCustomField.objects.annotate(
            has_unmatched_groups=Exists(unmatched_groups)
        ).filter(
            has_unmatched_groups=False
        ).values('id')

        def recurse(node):
            if node.children.exists():
                for child in node.children.all():
                    recurse(child)
            else:

                subprojects_qs = Subproject.objects.filter(administrative_level=node)

                subprojects_count = 0
                for subproject in subprojects_qs:
                    if len(subproject_custom_field_ids) - SubprojectFormResponse.objects.filter(
                            subproject__id=subproject.id, custom_form__id__in=subproject_custom_field_ids).count() > 0:
                        subprojects_count += 1
                descendants.append({
                    'id': node.id, 'name': node.name,
                    'pending_responses': subprojects_count if subprojects_count > 0 else '',
                })

        recurse(administrative_unit)
        return descendants
