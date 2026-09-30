"""Who can see and fill which forms and records.

One implementation for the MIS mobile web screens and the field app's API (merge plan Phase 2), so
the two can never disagree. The rules are the ones the mobile screens already applied:

- A form template (trackable object) or follow-up event is **listed** to a user who shares at
  least one group with it; follow-up events must also be active.
- **Filling** it needs the user to be in *every* group of the template or event (the rule the
  create/update screens enforce).
- A record (trackable-object instance) is visible when it is not restricted by administrative
  units, or one of its units is among the user's units, their ancestors or descendants. A field
  agent also always sees the records they created.
- A follow-up event is available on a record when it is linked to the record's trackable object,
  is listed to the user, and every event it depends on has a response for that record.
"""
from django.db.models import Exists, OuterRef, Q, Subquery

from administrativelevels.models import AdministrativeUnit
from trackableobjects.models import (
    FollowUpEvent,
    FollowUpEventDependency,
    FollowUpEventResponse,
    FollowUpEventTrackableObject,
    TrackableObject,
    TrackableObjectInstance,
)


def _group_ids(user):
    return list(user.groups.values_list("id", flat=True))


def accessible_unit_ids(user) -> set[int]:
    """The user's administrative units plus all their ancestors and descendants."""
    own = list(user.administrative_units.values_list("id", "parent_id"))
    ids = AdministrativeUnit.get_descendant_ids([pk for pk, _ in own])
    parents = {parent for _, parent in own if parent}
    while parents:
        ids |= parents
        parents = set(
            AdministrativeUnit.objects.filter(pk__in=parents, parent__isnull=False).values_list("parent_id", flat=True)
        ) - ids
    return ids


def listed_trackable_objects(user):
    matched = TrackableObject.groups.through.objects.filter(
        trackableobject_id=OuterRef("pk"), group_id__in=_group_ids(user)
    )
    return TrackableObject.objects.filter(Exists(matched))


def listed_follow_up_events(user):
    matched = FollowUpEvent.groups.through.objects.filter(
        followupevent_id=OuterRef("pk"), group_id__in=_group_ids(user)
    )
    return FollowUpEvent.objects.filter(Exists(matched), is_active=True)


def can_fill(user, template) -> bool:
    """Create/update rule: the user is in every group of the template or event."""
    required = set(template.groups.values_list("id", flat=True))
    return required <= set(_group_ids(user))


def visible_instances(user, unit_ids=None):
    """Records of listed trackable objects (or ones linked to listed events) the user may see."""
    unit_ids = accessible_unit_ids(user) if unit_ids is None else unit_ids
    linked_to_events = FollowUpEventTrackableObject.objects.filter(
        follow_up_event__in=listed_follow_up_events(user), trackable_object_id=OuterRef("trackable_object_id")
    )
    in_scope = Q(restrict_by_administrative_units=False) | Q(administrative_units__id__in=unit_ids)
    if getattr(user, "is_field_agent", False):
        in_scope |= Q(created_by=user)
    return (
        TrackableObjectInstance.objects.filter(in_scope)
        .filter(Q(trackable_object__in=listed_trackable_objects(user)) | Q(Exists(linked_to_events)))
        .distinct()
    )


def available_follow_up_events(user, instance):
    """Events the user can fill on ``instance`` now (dependencies met), ordered for display."""
    unfulfilled = FollowUpEventDependency.objects.filter(child_id=OuterRef("pk")).exclude(
        parent_id__in=Subquery(
            FollowUpEventResponse.objects.filter(trackable_object_instance=instance).values("follow_up_event_id")
        )
    )
    return (
        listed_follow_up_events(user)
        .filter(trackable_objects=instance.trackable_object)
        .annotate(has_unfulfilled_deps=Exists(unfulfilled))
        .filter(has_unfulfilled_deps=False)
        .distinct()
        .order_by("order", "name")
    )


def unmet_dependencies(event, instance) -> list[int]:
    """Parent event ids that still need a response on ``instance`` before ``event`` can be filled."""
    answered = set()
    if instance is not None:
        answered = set(
            FollowUpEventResponse.objects.filter(trackable_object_instance=instance).values_list(
                "follow_up_event_id", flat=True
            )
        )
    parents = FollowUpEventDependency.objects.filter(child=event).values_list("parent_id", flat=True)
    return [pk for pk in parents if pk not in answered]


def visible_responses(user, instance_ids=None):
    """Follow-up responses on visible records, plus the user's own standalone responses."""
    if instance_ids is None:
        instance_ids = visible_instances(user).values("id")
    return FollowUpEventResponse.objects.filter(
        Q(trackable_object_instance_id__in=instance_ids)
        | Q(trackable_object_instance__isnull=True, created_by=user)
    ).filter(follow_up_event__in=listed_follow_up_events(user))
