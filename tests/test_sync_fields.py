"""Offline groundwork: phone-generated IDs, answer versions and form schema versions."""
import copy
import uuid

import pytest
from django.db import IntegrityError
from django.urls import reverse

from trackableobjects.models import TrackableObject, TrackableObjectInstance

pytestmark = pytest.mark.django_db


def test_template_schema_version_goes_up_only_when_the_form_changes(trackable_object):
    assert trackable_object.schema_version == 1
    obj = TrackableObject.objects.get(pk=trackable_object.pk)
    obj.name = "Renamed"
    obj.save()
    assert obj.schema_version == 1
    schema = copy.deepcopy(obj.jsonForm)
    schema["form"][0]["page"]["properties"]["extra"] = {"type": "string"}
    obj.jsonForm = schema
    obj.save()
    assert TrackableObject.objects.get(pk=obj.pk).schema_version == 2


def test_new_answer_records_the_schema_version_it_was_filled_against(agent_client, trackable_object):
    TrackableObject.objects.filter(pk=trackable_object.pk).update(schema_version=3)
    url = reverse("trackableobjects:mobile:trackable_object_create", kwargs={"pk": trackable_object.pk})
    agent_client.post(url, {"name": "École B", "ok": "True"})
    created = TrackableObjectInstance.objects.get()
    assert created.schema_version == 3
    assert created.version == 1


def test_answer_version_goes_up_when_answers_change(agent_client, instance):
    instance = TrackableObjectInstance.objects.get(pk=instance.pk)
    instance.save()
    assert instance.version == 1  # saved without changes
    url = reverse("trackableobjects:mobile:trackable_object_edit", kwargs={"pk": instance.pk})
    agent_client.post(url, {"name": "École A2", "ok": "True"})
    assert TrackableObjectInstance.objects.get(pk=instance.pk).version == 2


def test_version_is_saved_with_update_fields(instance):
    instance = TrackableObjectInstance.objects.get(pk=instance.pk)
    instance.jsonForm = {"name": "changed"}
    instance.save(update_fields=["jsonForm"])
    assert TrackableObjectInstance.objects.get(pk=instance.pk).version == 2


def test_client_uuid_is_unique(instance, trackable_object, agent):
    key = uuid.uuid4()
    TrackableObjectInstance.objects.filter(pk=instance.pk).update(client_uuid=key)
    with pytest.raises(IntegrityError):
        TrackableObjectInstance.objects.create(trackable_object=trackable_object, created_by=agent, client_uuid=key)


def test_answers_without_client_uuid_coexist(instance, trackable_object, agent):
    TrackableObjectInstance.objects.create(trackable_object=trackable_object, created_by=agent)
    assert TrackableObjectInstance.objects.filter(client_uuid__isnull=True).count() == 2
