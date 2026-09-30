"""Shared fixtures: one staff user, one field agent, and a small form setup.

Forms use the real schema shape (a dict with "form" pages). Answers are a flat dict.
"""
import pytest
from django.contrib.auth.models import Group
from django.test import Client

from administrativelevels.models import AdministrativeLevel, AdministrativeUnit
from authorization.models import CustomUser
from trackableobjects.models import (
    FollowUpEvent,
    FollowUpEventResponse,
    FollowUpEventTrackableObject,
    TrackableObject,
    TrackableObjectInstance,
)

SCHEMA = {
    "form": [
        {
            "page": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "ok": {"type": "boolean"}},
                "required": ["name"],
            },
            "options": {"fields": {"name": {"label": "Name", "order": 1}, "ok": {"label": "OK", "order": 2}}},
        }
    ]
}


@pytest.fixture(autouse=True)
def _hosts(settings):
    settings.ALLOWED_HOSTS = ["testserver"]


@pytest.fixture
def unit(db):
    level = AdministrativeLevel.objects.create(name="Commune", order=1)
    return AdministrativeUnit.objects.create(name="Cotonou", level=level)


@pytest.fixture
def tf_group(db):
    return Group.objects.get_or_create(name="Technical facilitator")[0]


@pytest.fixture
def staff_user(db):
    return CustomUser.objects.create_user(email="staff@example.test", password="x", is_staff=True)


@pytest.fixture
def superuser(db):
    return CustomUser.objects.create_superuser(email="root@example.test", password="x")


@pytest.fixture
def agent(db, unit, tf_group):
    user = CustomUser.objects.create_user(email="agent@example.test", password="x", is_field_agent=True)
    user.groups.add(tf_group)
    user.administrative_units.add(unit)
    return user


@pytest.fixture
def other_agent(db):
    """A field agent in no group and no unit."""
    return CustomUser.objects.create_user(email="other@example.test", password="x", is_field_agent=True)


def client_for(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def staff_client(staff_user):
    return client_for(staff_user)


@pytest.fixture
def agent_client(agent):
    return client_for(agent)


@pytest.fixture
def trackable_object(db, staff_user, tf_group):
    obj = TrackableObject.objects.create(name="School", jsonForm=SCHEMA, created_by=staff_user, identifier_field="name")
    obj.groups.add(tf_group)
    return obj


@pytest.fixture
def follow_up_event(db, staff_user, tf_group, trackable_object):
    event = FollowUpEvent.objects.create(name="Inspection", jsonForm=SCHEMA, created_by=staff_user)
    event.groups.add(tf_group)
    FollowUpEventTrackableObject.objects.create(follow_up_event=event, trackable_object=trackable_object)
    return event


@pytest.fixture
def instance(db, agent, tf_group, unit, trackable_object):
    inst = TrackableObjectInstance.objects.create(
        trackable_object=trackable_object, created_by=agent, jsonForm={"name": "École A", "ok": True}
    )
    inst.groups.add(tf_group)
    inst.administrative_units.add(unit)
    return inst


@pytest.fixture
def response(db, agent, follow_up_event, instance):
    return FollowUpEventResponse.objects.create(
        follow_up_event=follow_up_event, trackable_object_instance=instance, created_by=agent, jsonForm={"name": "visit"}
    )
