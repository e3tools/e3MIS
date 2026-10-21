"""Forms filled during a worksite visit (Brice, 8 Oct 2026: "each form is linked to the site
visit and to the check-in").

The phone tags a record or follow-up response with the visit's check-in idempotency key
(``visit_key``). Forms and visits travel separately and either may reach the server first, so the
key is stored as sent and the ``visit`` link is set by whichever arrives second.
"""


def find_visit(user, key):
    from fieldmonitoring.visits.models import Visit

    if not key:
        return None
    return Visit.objects.filter(user=user, checkin_idempotency_key=key).select_related("worksite").first()


def attach(obj, user, key) -> None:
    """Store the visit key on a new record or response and link the visit if it is known."""
    if not key:
        return
    obj.visit_key = str(key)[:64]
    obj.visit = find_visit(user, key)
    obj.save(update_fields=["visit_key", "visit"])


def link_waiting_forms(visit) -> None:
    from .models import FollowUpEventResponse, TrackableObjectInstance

    key = visit.checkin_idempotency_key
    for model in (TrackableObjectInstance, FollowUpEventResponse):
        model.objects.filter(visit_key=key, visit__isnull=True, created_by=visit.user).update(visit=visit)
    # A sub-project identified the same day just before its first check-in (a new site has to
    # exist before anyone can check in there) belongs to that first visit.
    from fieldmonitoring.core import clock

    instance = visit.worksite.trackable_object_instance
    if (
        instance is not None
        and instance.visit_id is None
        and instance.created_by_id == visit.user_id
        and clock.local_date(instance.created_at) == clock.local_date(visit.checked_in_at)
        and not instance.stage_changes.exists()
    ):
        TrackableObjectInstance.objects.filter(pk=instance.pk).update(visit=visit, visit_key=key)
