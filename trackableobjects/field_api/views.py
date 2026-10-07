"""Forms API for the field app (merge plan Phase 2), offline-first.

- ``GET  /api/v1/forms/sync/?since=<iso>``  everything the phone keeps locally; with ``since``,
  only records and responses changed after it (templates, events and units always come in full,
  they are small), plus the full id lists so the phone can drop what it may no longer see.
- ``POST /api/v1/forms/push/``  a batch of creates/updates made on the phone, applied in order,
  each answered separately. Replaying an item is harmless (``client_uuid`` / ``base_version``).
- ``POST /api/v1/forms/attachments/``  one file for a record or response, idempotent by
  ``client_uuid``. ``GET /api/v1/forms/attachments/<id>/`` streams it after a permission check.

Every submission is re-checked with the MIS form parser (``validation.py``).
"""
from django.db import IntegrityError, transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from administrativelevels.models import AdministrativeUnit
from subprojects.models import Attachment
from trackableobjects import lifecycle, visibility
from trackableobjects.models import (
    FollowUpEvent,
    FollowUpEventDependency,
    FollowUpEventResponse,
    FollowUpEventTrackableObject,
    TrackableObject,
    TrackableObjectInstance,
)

from .validation import ATTACHMENT, pages, validate_answers

MAX_ITEMS = 100


class IsFieldAgent(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_field_agent)


# --- serialization ---------------------------------------------------------------------------


def _attachment(a: Attachment) -> dict:
    return {
        "id": a.id,
        "client_uuid": str(a.client_uuid) if a.client_uuid else None,
        "field_name": a.field_name,
        "url": f"/api/v1/forms/attachments/{a.id}/",
    }


def _record(instance, user, attachments) -> dict:
    return {
        "id": instance.id,
        "client_uuid": str(instance.client_uuid) if instance.client_uuid else None,
        "trackable_object_id": instance.trackable_object_id,
        "identifier": str(instance.identifier),
        "answers": instance.jsonForm if isinstance(instance.jsonForm, dict) else {},
        "stage": instance.stage,
        "version": instance.version,
        "schema_version": instance.schema_version,
        "created_by_me": instance.created_by_id == user.id,
        "created_at": instance.created_at,
        "updated_at": instance.updated_at,
        "attachments": attachments.get(instance.id, []),
    }


def _response(response, user, attachments) -> dict:
    return {
        "id": response.id,
        "client_uuid": str(response.client_uuid) if response.client_uuid else None,
        "follow_up_event_id": response.follow_up_event_id,
        "record_id": response.trackable_object_instance_id,
        "answers": response.jsonForm if isinstance(response.jsonForm, dict) else {},
        "version": response.version,
        "schema_version": response.schema_version,
        "created_by_me": response.created_by_id == user.id,
        "created_at": response.created_at,
        "updated_at": response.updated_at,
        "attachments": attachments.get(response.id, []),
    }


def _schema_fields(schema):
    for page in pages(schema):
        yield from page.get("page", {}).get("properties", {}).items()


# --- sync --------------------------------------------------------------------------------------


class SyncView(APIView):
    permission_classes = [IsFieldAgent]

    @extend_schema(parameters=[OpenApiParameter("since", OpenApiTypes.DATETIME)], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        user = request.user
        server_time = timezone.now()
        since = None
        if raw := request.query_params.get("since"):
            since = parse_datetime(raw)
            if since is None:
                raise ValidationError({"since": "Use an ISO 8601 date-time."})
            if timezone.is_naive(since):
                since = timezone.make_aware(since, timezone.utc)

        unit_ids = visibility.accessible_unit_ids(user)
        listed_tos = set(visibility.listed_trackable_objects(user).values_list("id", flat=True))
        events = list(visibility.listed_follow_up_events(user).prefetch_related("groups"))
        event_ids = [e.id for e in events]
        links = {}
        for link in FollowUpEventTrackableObject.objects.filter(follow_up_event_id__in=event_ids):
            links.setdefault(link.follow_up_event_id, []).append(link.trackable_object_id)
        parents = {}
        for dep in FollowUpEventDependency.objects.filter(child_id__in=event_ids):
            parents.setdefault(dep.child_id, []).append(dep.parent_id)
        to_ids = listed_tos | {pk for ids in links.values() for pk in ids}
        trackable_objects = TrackableObject.objects.filter(id__in=to_ids).prefetch_related("groups")
        user_groups = set(user.groups.values_list("id", flat=True))

        def fillable(template):
            return {g.id for g in template.groups.all()} <= user_groups

        instances = visibility.visible_instances(user, unit_ids)
        instance_ids = list(instances.values_list("id", flat=True))
        responses = visibility.visible_responses(user, instance_ids)
        response_ids = list(responses.values_list("id", flat=True))
        changed_instances = TrackableObjectInstance.objects.filter(id__in=instance_ids)
        changed_responses = FollowUpEventResponse.objects.filter(id__in=response_ids)
        if since is not None:
            changed_instances = changed_instances.filter(updated_at__gt=since)
            changed_responses = changed_responses.filter(updated_at__gt=since)
        changed_instances = list(changed_instances.select_related("trackable_object"))
        changed_responses = list(changed_responses)

        record_files, response_files = {}, {}
        for a in Attachment.objects.filter(trackable_object_instance__in=[i.id for i in changed_instances]):
            record_files.setdefault(a.trackable_object_instance_id, []).append(_attachment(a))
        for a in Attachment.objects.filter(follow_up_event_response__in=[r.id for r in changed_responses]):
            response_files.setdefault(a.follow_up_event_response_id, []).append(_attachment(a))

        schemas = [t.jsonForm for t in trackable_objects] + [e.jsonForm for e in events]
        return Response({
            "server_time": server_time,
            "full": since is None,
            "trackable_objects": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "icon": t.icon,
                    "color": t.color_solid,
                    "identifier_field": t.identifier_field,
                    "schema": t.jsonForm,
                    "schema_version": t.schema_version,
                    "can_create": t.id in listed_tos and fillable(t),
                    "stages": t.stages or [],
                    "creates_worksite": t.creates_worksite,
                    "updated_at": t.updated_at,
                }
                for t in trackable_objects
            ],
            "follow_up_events": [
                {
                    "id": e.id,
                    "name": e.name,
                    "description": e.description,
                    "identifier_field": e.identifier_field,
                    "is_one_off": e.is_one_off,
                    "order": e.order,
                    "trackable_object_ids": links.get(e.id, []),
                    "standalone": not links.get(e.id),
                    "depends_on": parents.get(e.id, []),
                    "stages": e.stages or [],
                    "stage_rules": e.stage_rules or [],
                    "schema": e.jsonForm,
                    "schema_version": e.schema_version,
                    "can_fill": fillable(e),
                    "updated_at": e.updated_at,
                }
                for e in events
            ],
            "administrative_units": self._units(unit_ids, schemas),
            # For pickers restricted to "my units": the user's units and their descendants.
            "my_unit_ids": sorted(AdministrativeUnit.get_descendant_ids(user.administrative_units.values_list("id", flat=True))),
            "trackable_object_options": self._trackable_object_options(user, schemas),
            "records": [_record(i, user, record_files) for i in changed_instances],
            "record_ids": instance_ids,
            "responses": [_response(r, user, response_files) for r in changed_responses],
            "response_ids": response_ids,
        })

    @staticmethod
    def _units(unit_ids, schemas):
        """The user's units (with ancestors/descendants), plus the tree down to the deepest level any
        unrestricted administrative-level field asks for, so pickers work offline."""
        extra_orders = []
        for schema in schemas:
            for _, field in _schema_fields(schema):
                if field.get("type") != "administrative_level":
                    continue
                validators = field.get("validators", {})
                if validators.get("administrative_level_restriction") == "true":
                    continue
                extra_orders.append(int(validators.get("max_admin_level_order") or 10_000))
        units = AdministrativeUnit.objects.filter(id__in=unit_ids)
        if extra_orders:
            units = units | AdministrativeUnit.objects.filter(level__order__lte=max(extra_orders))
        return [
            {"id": u.id, "name": u.name, "parent_id": u.parent_id, "level": u.level.name, "level_order": u.level.order}
            for u in units.select_related("level").distinct().order_by("level__order", "name")
        ]

    @staticmethod
    def _trackable_object_options(user, schemas):
        """Choices for 'trackable_object' fields, keyed by trackable object id."""
        wanted, restricted = set(), set()
        for schema in schemas:
            for _, field in _schema_fields(schema):
                if field.get("type") != "trackable_object":
                    continue
                validators = field.get("validators", {})
                if validators.get("trackable_object_id"):
                    to_id = int(validators["trackable_object_id"])
                    wanted.add(to_id)
                    if validators.get("administrative_level_restriction") == "true":
                        restricted.add(to_id)
        options = {}
        own_units = None
        for to_id in wanted:
            qs = TrackableObjectInstance.objects.filter(trackable_object_id=to_id).select_related("trackable_object")
            if to_id in restricted:
                if own_units is None:
                    own_units = AdministrativeUnit.get_descendant_ids(
                        user.administrative_units.values_list("id", flat=True)
                    )
                qs = qs.filter(administrative_units__id__in=own_units).distinct()
            options[str(to_id)] = [{"id": i.id, "label": str(i.identifier)} for i in qs]
        return options


# --- push --------------------------------------------------------------------------------------


class ItemError(Exception):
    def __init__(self, status_, **extra):
        super().__init__(status_)
        self.status = status_
        self.extra = extra


class PushView(APIView):
    permission_classes = [IsFieldAgent]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        items = request.data.get("items") if isinstance(request.data, dict) else None
        if not isinstance(items, list):
            raise ValidationError({"items": "Send a list of items."})
        if len(items) > MAX_ITEMS:
            raise ValidationError({"items": f"At most {MAX_ITEMS} items per request."})
        results = []
        for item in items:
            try:
                with transaction.atomic():
                    results.append(self._apply(request.user, item))
            except ItemError as exc:
                results.append({"client_uuid": _key(item), "status": exc.status, **exc.extra})
        return Response({"server_time": timezone.now(), "results": results})

    def _apply(self, user, item):
        if not isinstance(item, dict):
            raise ItemError("invalid", errors={"__all__": ["Each item must be an object."]})
        kind, op = item.get("kind"), item.get("op")
        if kind not in ("record", "response") or op not in ("create", "update"):
            raise ItemError("invalid", errors={"__all__": ["kind must be record|response, op create|update."]})
        model = TrackableObjectInstance if kind == "record" else FollowUpEventResponse
        if op == "create":
            client_uuid = item.get("client_uuid")
            if not client_uuid:
                raise ItemError("invalid", errors={"client_uuid": ["Required for create."]})
            existing = model.objects.filter(client_uuid=client_uuid).first()
            if existing is not None:
                if existing.created_by_id != user.id:
                    raise ItemError("forbidden")
                return _done("duplicate", existing, item)
            return self._create_record(user, item) if kind == "record" else self._create_response(user, item)
        return self._update(user, item, model)

    # records

    def _create_record(self, user, item):
        template = TrackableObject.objects.filter(pk=item.get("trackable_object_id")).first()
        if template is None:
            raise ItemError("not_found")
        if not visibility.listed_trackable_objects(user).filter(pk=template.pk).exists() or not visibility.can_fill(
            user, template
        ):
            raise ItemError("forbidden")
        answers = _validated(template.jsonForm, item.get("answers"), user)
        try:
            instance = TrackableObjectInstance.objects.create(
                trackable_object=template, created_by=user, jsonForm=answers, client_uuid=item["client_uuid"]
            )
        except (IntegrityError, ValueError):
            raise ItemError("invalid", errors={"client_uuid": ["Not a valid UUID."]}) from None
        lifecycle.on_record_created(instance, user)
        return _done("created", instance, item)

    # responses

    def _create_response(self, user, item):
        event = FollowUpEvent.objects.filter(pk=item.get("follow_up_event_id")).first()
        if event is None:
            raise ItemError("not_found")
        if not visibility.listed_follow_up_events(user).filter(pk=event.pk).exists() or not visibility.can_fill(
            user, event
        ):
            raise ItemError("forbidden")
        instance = _resolve_record(user, item.get("record_id"), item.get("record_client_uuid"))
        linked = set(event.trackable_objects.values_list("id", flat=True))
        if instance is None and linked:
            raise ItemError("invalid", errors={"record_id": ["This follow-up event needs a record."]})
        if instance is not None and instance.trackable_object_id not in linked:
            raise ItemError("invalid", errors={"record_id": ["This follow-up event does not apply to this record."]})
        if missing := visibility.unmet_dependencies(event, instance):
            raise ItemError("invalid", errors={"__all__": ["Earlier follow-up events must be filled first."]},
                            depends_on=missing)
        if event.is_one_off:
            earlier = FollowUpEventResponse.objects.filter(follow_up_event=event, trackable_object_instance=instance)
            if instance is None:
                earlier = earlier.filter(created_by=user)
            if existing := earlier.first():
                raise ItemError("conflict", reason="already_answered", server=_response(existing, user, {}))
        answers = _validated(event.jsonForm, item.get("answers"), user, _parent_data(event, instance))
        try:
            response = FollowUpEventResponse.objects.create(
                follow_up_event=event, trackable_object_instance=instance, created_by=user, jsonForm=answers,
                client_uuid=item["client_uuid"],
            )
        except (IntegrityError, ValueError):
            raise ItemError("invalid", errors={"client_uuid": ["Not a valid UUID."]}) from None
        # Never rejected for the stage (answers made offline may arrive late); the stage only moves
        # when the event was open in it.
        lifecycle.apply_response(response, user)
        return _done("created", response, item)

    # updates

    def _update(self, user, item, model):
        target = None
        if item.get("id") is not None:
            target = model.objects.filter(pk=item["id"]).first()
        elif item.get("client_uuid"):
            target = model.objects.filter(client_uuid=item["client_uuid"]).first()
        if target is None:
            raise ItemError("not_found")
        if not request_view_check(user, target):
            raise ItemError("forbidden")
        base = item.get("base_version")
        if not isinstance(base, int):
            raise ItemError("invalid", errors={"base_version": ["Required for update."]})
        if model is TrackableObjectInstance:
            template, parent = target.trackable_object, {}
            server_copy = lambda: _record(target, user, {})  # noqa: E731
        else:
            template = target.follow_up_event
            parent = _parent_data(template, target.trackable_object_instance)
            server_copy = lambda: _response(target, user, {})  # noqa: E731
        if not visibility.can_fill(user, template):
            raise ItemError("forbidden")
        answers = _validated(template.jsonForm, item.get("answers"), user, parent)
        if target.version != base:
            if target.jsonForm == answers:
                return _done("duplicate", target, item)
            raise ItemError("conflict", reason="stale", server=server_copy())
        target = type(target).objects.select_for_update().get(pk=target.pk)
        if target.version != base:
            raise ItemError("conflict", reason="stale", server=server_copy())
        target.jsonForm = answers
        target.save()
        if model is TrackableObjectInstance:
            lifecycle.on_record_updated(target, user)
        else:
            lifecycle.apply_response(target, user)
        return _done("updated", target, item)


def request_view_check(user, target) -> bool:
    if isinstance(target, TrackableObjectInstance):
        return visibility.visible_instances(user).filter(pk=target.pk).exists()
    return visibility.visible_responses(user).filter(pk=target.pk).exists()


def _key(item):
    if isinstance(item, dict):
        return item.get("client_uuid") or item.get("id")
    return None


def _done(status_, obj, item) -> dict:
    return {"client_uuid": _key(item), "status": status_, "id": obj.id, "version": obj.version}


def _validated(schema, answers, user, parent=None):
    clean, errors = validate_answers(schema, answers, user=user, parent_data=parent)
    if errors:
        raise ItemError("invalid", errors=errors)
    return clean


def _resolve_record(user, record_id, record_client_uuid):
    if record_id is None and not record_client_uuid:
        return None
    qs = visibility.visible_instances(user)
    instance = (
        qs.filter(pk=record_id).first() if record_id is not None else qs.filter(client_uuid=record_client_uuid).first()
    )
    if instance is None:
        raise ItemError("invalid", errors={"record_id": ["Unknown record."]})
    return instance


def _parent_data(event, instance) -> dict:
    """What parent-form display conditions look at: the record's answers, then the latest response
    of each event this one depends on (same as the MIS follow-up screen)."""
    data = {}
    if instance is None:
        return data
    if isinstance(instance.jsonForm, dict):
        data.update(instance.jsonForm)
    for dep in event.dependencies_children.select_related("parent"):
        latest = (
            FollowUpEventResponse.objects.filter(follow_up_event=dep.parent, trackable_object_instance=instance)
            .order_by("-created_at")
            .first()
        )
        if latest and isinstance(latest.jsonForm, dict):
            data.update(latest.jsonForm)
    return data


# --- attachments -------------------------------------------------------------------------------


class AttachmentUploadView(APIView):
    permission_classes = [IsFieldAgent]
    parser_classes = [MultiPartParser]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        user, data = request.user, request.data
        client_uuid, kind, field_name = data.get("client_uuid"), data.get("kind"), data.get("field_name")
        upload = request.FILES.get("file")
        if not (client_uuid and kind in ("record", "response") and field_name and upload):
            raise ValidationError("Send client_uuid, kind (record|response), owner, field_name and file.")
        if existing := Attachment.objects.filter(client_uuid=client_uuid).first():
            return Response({"status": "duplicate", **_attachment(existing)})
        model = TrackableObjectInstance if kind == "record" else FollowUpEventResponse
        owner = None
        if data.get("owner_id"):
            owner = model.objects.filter(pk=data["owner_id"]).first()
        elif data.get("owner_client_uuid"):
            owner = model.objects.filter(client_uuid=data["owner_client_uuid"]).first()
        if owner is None:
            return Response({"detail": "Unknown owner; push the record first."}, status=status.HTTP_404_NOT_FOUND)
        template = owner.trackable_object if kind == "record" else owner.follow_up_event
        if not request_view_check(user, owner) or not visibility.can_fill(user, template):
            raise PermissionDenied()
        if (owner.jsonForm or {}).get(field_name) != ATTACHMENT:
            raise ValidationError({"field_name": "The answers do not expect a file for this field."})
        link = {"trackable_object_instance": owner} if kind == "record" else {"follow_up_event_response": owner}
        try:
            with transaction.atomic():
                attachment = Attachment.objects.create(client_uuid=client_uuid, field_name=field_name, file=upload, **link)
        except IntegrityError:
            attachment = Attachment.objects.get(client_uuid=client_uuid)
            return Response({"status": "duplicate", **_attachment(attachment)})
        except ValueError:
            raise ValidationError({"client_uuid": "Not a valid UUID."}) from None
        # Touch the owner so a delta sync picks up the new file.
        type(owner).objects.filter(pk=owner.pk).update(updated_at=timezone.now())
        return Response({"status": "created", **_attachment(attachment)}, status=status.HTTP_201_CREATED)


class AttachmentDownloadView(APIView):
    permission_classes = [IsFieldAgent]

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    def get(self, request, attachment_id):
        attachment = get_object_or_404(Attachment, pk=attachment_id)
        owner = attachment.trackable_object_instance or attachment.follow_up_event_response
        if owner is None or not request_view_check(request.user, owner):
            raise PermissionDenied()
        return FileResponse(attachment.file.open("rb"), filename=attachment.file.name.rsplit("/", 1)[-1])

