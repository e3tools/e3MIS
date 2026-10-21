"""Read-only API at /api/v1/: JWT or API token, desktop users only."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

READ_ENDPOINTS = [
    "trackable-object/",
    "trackable-object-instance/",
    "follow-up-event/",
    "follow-up-event-response/",
    "follow-up-event-dependency/",
    "user/",
]


def jwt_client(email):
    c = APIClient()
    r = c.post(reverse("authorization:token_obtain_pair"), {"email": email, "password": "x"}, format="json")
    assert r.status_code == 200
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.json()['access']}")
    return c


@pytest.mark.parametrize("path", READ_ENDPOINTS)
def test_desktop_user_reads_with_jwt(staff_user, trackable_object, follow_up_event, instance, response, path):
    r = jwt_client(staff_user.email).get(f"/fr/api/v1/{path}")
    assert r.status_code == 200, r.content


@pytest.mark.parametrize("path", READ_ENDPOINTS)
def test_anonymous_cannot_read(instance, path):
    assert APIClient().get(f"/fr/api/v1/{path}").status_code == 401


@pytest.mark.parametrize("path", READ_ENDPOINTS)
def test_field_agent_cannot_read_everything(agent, path):
    assert jwt_client(agent.email).get(f"/fr/api/v1/{path}").status_code == 403


def test_api_is_read_only(staff_user, trackable_object):
    r = jwt_client(staff_user.email).post("/fr/api/v1/trackable-object/", {"name": "x"}, format="json")
    assert r.status_code == 403


def test_api_token_authenticates(staff_user, trackable_object):
    from api.models import ApiToken

    raw, _ = ApiToken.mint(user=staff_user, name="integration")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
    assert c.get("/fr/api/v1/trackable-object/").status_code == 200


def test_malformed_api_token_is_rejected(instance):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION="Bearer MIS-deadbeef.wrong")
    assert c.get("/fr/api/v1/trackable-object/").status_code == 401
