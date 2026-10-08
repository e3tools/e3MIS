"""Record lifecycle: which follow-up forms are open at each stage of a record.

A record type (``TrackableObject.stages``) may list stages, for a sub-project:
works → acceptance → accepted, plus postponed and terminated. A record starts in the first one.
Each follow-up event lists the stages it can be filled in (``FollowUpEvent.stages``) and how an
answer moves the record on (``FollowUpEvent.stage_rules``): "Travaux achevés" in an inspection opens
the acceptance form, an accepted handover closes the inspections and opens the post-handover
follow-up, a definitive stop terminates the record.

Rules only move a record when the event was open in its current stage. An answer made offline for
a stage the record has since left is kept, but moves nothing. Leaving a stage with no open events
(terminated) is a person's decision: ``reopen``. The tool records what happened, it does not block
anyone (non-negotiable 5): the field API never rejects an answer because of the stage.

The same rules run on the phone (mobile ``src/lib/forms/lifecycle.ts``) so forms open offline.
"""
from django.db import transaction

from utils.json_form_parser import evaluate_condition

from .models import FollowUpEvent, RecordStageChange, TrackableObject, TrackableObjectInstance


def stage_keys(template: TrackableObject) -> list[str]:
    return [s["key"] for s in template.stages or [] if isinstance(s, dict) and s.get("key")]


def stage_label(template: TrackableObject, key: str) -> str:
    for s in template.stages or []:
        if isinstance(s, dict) and s.get("key") == key:
            return s.get("label") or key
    return key


def initial_stage(template: TrackableObject) -> str:
    keys = stage_keys(template)
    return keys[0] if keys else ""


def is_open(event: FollowUpEvent, instance: TrackableObjectInstance | None) -> bool:
    """Whether ``event`` can be filled on ``instance`` in its current stage."""
    if instance is None or not event.stages or not stage_keys(instance.trackable_object):
        return True
    return instance.stage in event.stages


def next_stage(event: FollowUpEvent, answers) -> str | None:
    """The stage the first matching rule of ``event`` sends a record to, if any."""
    if not isinstance(answers, dict):
        return None
    for rule in event.stage_rules or []:
        if not isinstance(rule, dict) or not rule.get("to"):
            continue
        if evaluate_condition(answers.get(rule.get("field")), rule.get("operator", "equals"), rule.get("value", "")):
            return rule["to"]
    return None


def apply_response(response, user=None) -> str | None:
    """Move the response's record as the event's rules say. Returns the new stage, or None."""
    instance = response.trackable_object_instance
    event = response.follow_up_event
    if instance is None or not is_open(event, instance):
        return None
    target = next_stage(event, response.jsonForm)
    if target is None or target == instance.stage or target not in stage_keys(instance.trackable_object):
        return None
    _move(instance, target, user=user, response=response)
    return target


def reopen_target(instance: TrackableObjectInstance) -> str:
    """The stage the record was in before its current one (the first stage if unknown)."""
    last = instance.stage_changes.filter(to_stage=instance.stage).exclude(from_stage="").first()
    return last.from_stage if last else initial_stage(instance.trackable_object)


def reopen(instance: TrackableObjectInstance, user, note: str = "") -> str:
    """Send a record back to the stage it was in before its current one (a supervisor's decision)."""
    target = reopen_target(instance)
    if target and target != instance.stage:
        _move(instance, target, user=user, note=note)
    return instance.stage


@transaction.atomic
def _move(instance, target, *, user=None, response=None, note=""):
    RecordStageChange.objects.create(
        instance=instance, from_stage=instance.stage, to_stage=target, response=response, changed_by=user, note=note
    )
    instance.stage = target
    # updated_at moves too, so the phones pick the new stage up on their next sync.
    instance.save(update_fields=["stage", "updated_at"])


def on_record_created(instance: TrackableObjectInstance, user, worksite_id=None) -> None:
    """Start the lifecycle, and create (or complete) the worksite when the record type is one.

    ``worksite_id``: the site the agent checked in at when filling the form, e.g. one just added
    from the field as "not listed". The record then describes that site instead of a new one.
    """
    if not instance.stage and (first := initial_stage(instance.trackable_object)):
        instance.stage = first
        instance.save(update_fields=["stage"])
    if instance.trackable_object.creates_worksite:
        create_worksite(instance, user, worksite_id=worksite_id)


# --- worksites -------------------------------------------------------------------------------


def _fields(schema):
    from .field_api.validation import pages

    found = []
    for page in pages(schema):
        options = page.get("options", {}).get("fields", {})
        for name, prop in page.get("page", {}).get("properties", {}).items():
            found.append((options.get(name, {}).get("order", 0), name, prop))
    return [(name, prop) for _, name, prop in sorted(found, key=lambda f: f[0])]


def _first_answer(instance, field_type):
    answers = instance.jsonForm if isinstance(instance.jsonForm, dict) else {}
    for name, prop in _fields(instance.trackable_object.jsonForm):
        if prop.get("type") == field_type and answers.get(name) not in (None, ""):
            return answers[name]
    return None


def _location(value):
    try:
        parts = [float(p) for p in str(value).replace(",", " ").split()]
    except ValueError:
        return None
    if len(parts) < 2 or not (-90 <= parts[0] <= 90 and -180 <= parts[1] <= 180):
        return None
    return parts[0], parts[1], (parts[2] if len(parts) > 2 else None)


def _existing_site(instance, user, worksite_id):
    """The visited site this record should describe: named by the phone or by the linked visit,
    not yet describing another record, and created by or assigned to the agent."""
    from fieldmonitoring.registry.models import Worksite

    candidates = []
    if worksite_id:
        candidates.append(Worksite.objects.filter(pk=worksite_id).first() if _is_uuid(worksite_id) else None)
    if instance.visit_id:
        candidates.append(instance.visit.worksite)
    for site in candidates:
        if site is None or site.trackable_object_instance_id is not None:
            continue
        if site.created_by_id == getattr(user, "pk", None) or site.assignments.filter(
            user=user, unassigned_on__isnull=True
        ).exists():
            return site
    return None


def _is_uuid(value) -> bool:
    import uuid

    try:
        uuid.UUID(str(value))
    except ValueError:
        return False
    return True


def create_worksite(instance: TrackableObjectInstance, user, worksite_id=None):
    """The worksite visits attach to, from a record such as a sub-project identification form.

    - village: the record's first administrative-level answer (and the record is placed in it);
    - name: the record's identifier;
    - coordinates: the first location answer, as a *pending* capture. The worksite has no geofence
      until a supervisor confirms it, so check-ins are unverified until then (BR-9), never missed;
    - the agent who filled the form is assigned to it.

    When the agent filled the form at a site that has no record yet (checked in at a site added
    from the field), that site is completed instead of creating another one.

    Returns None when the record names no village. Idempotent.
    """
    from administrativelevels.models import AdministrativeUnit
    from fieldmonitoring.core import clock
    from fieldmonitoring.registry.models import Worksite, WorksiteAssignment

    if existing := Worksite.objects.filter(trackable_object_instance=instance).first():
        return existing
    try:
        village = AdministrativeUnit.objects.filter(pk=int(_first_answer(instance, "administrative_level"))).first()
    except (TypeError, ValueError):
        village = None
    name = str(instance.identifier)[:200]
    if site := _existing_site(instance, user, worksite_id):
        # The agent checked in at this site and identified it: the form completes it.
        site.trackable_object_instance = instance
        site.name = name
        if village is not None and site.location is None and village.pk != site.village_id:
            from fieldmonitoring.core.geography import commune_of, region_of
            from fieldmonitoring.core.models import ProgrammeConfig

            site.village, site.commune, site.region = village, commune_of(village), region_of(village)
            site.tolerance_m = ProgrammeConfig.get().tolerance_for(village)
        site.save()
        instance.administrative_units.add(site.village)
        if site.location is None:
            _pending_coordinate(instance, site, user)
        return site
    if village is None:
        return None
    instance.administrative_units.add(village)
    worksite = Worksite.objects.create(
        name=name,
        code=f"{instance.display_id}",
        village=village,
        is_provisional=True,
        created_by=user,
        trackable_object_instance=instance,
    )
    _pending_coordinate(instance, worksite, user)
    if user is not None and getattr(user, "records_visits", False):
        WorksiteAssignment.objects.create(user=user, worksite=worksite, assigned_on=clock.today())
    return worksite


def _pending_coordinate(instance, worksite, user):
    from fieldmonitoring.registry.models import ProvisionalCoordinate
    from fieldmonitoring.visits.services import make_point

    if (where := _location(_first_answer(instance, "geolocation"))) and user is not None:
        lat, lng, accuracy = where
        ProvisionalCoordinate.objects.create(
            worksite=worksite,
            location=make_point(lat, lng),
            accuracy_m=round(accuracy) if accuracy is not None else None,
            captured_by=user,
            visit=instance.visit,
        )


def on_record_updated(instance: TrackableObjectInstance, user) -> None:
    """Keep the worksite's name in step with the record, or create it if the village came later."""
    if not instance.trackable_object.creates_worksite:
        return
    from fieldmonitoring.registry.models import Worksite

    worksite = Worksite.objects.filter(trackable_object_instance=instance).first()
    if worksite is None:
        create_worksite(instance, user)
    elif worksite.name != (name := str(instance.identifier)[:200]):
        worksite.name = name
        worksite.save(update_fields=["name"])
