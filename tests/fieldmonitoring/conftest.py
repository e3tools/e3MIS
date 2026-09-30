import io
import uuid
from datetime import date, datetime, timedelta

import pytest
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from authorization.models import Role, User
from fieldmonitoring.core.models import ProgrammeConfig
from administrativelevels.models import AdministrativeLevel, AdministrativeUnit
from fieldmonitoring.registry.models import Worksite, WorksiteAssignment

# A point near Séguéla, and helpers to move a known number of metres from it.
BASE_LAT, BASE_LNG = 7.9611, -6.6731


def north_of(lat, lng, metres):
    return lat + metres / 111_320, lng


@pytest.fixture(autouse=True)
def config(db):
    config = ProgrammeConfig.get()
    config.timezone = "Africa/Abidjan"
    config.save()
    return config


@pytest.fixture
def levels(db):
    """Region → Commune → Village, mapped in ProgrammeConfig like a real deployment."""
    region = AdministrativeLevel.objects.create(name="Région", order=1)
    commune = AdministrativeLevel.objects.create(name="Commune", order=2)
    village = AdministrativeLevel.objects.create(name="Village", order=3)
    config = ProgrammeConfig.get()
    config.region_level, config.commune_level, config.village_level = region, commune, village
    config.save()
    return {"region": region, "commune": commune, "village": village}


@pytest.fixture
def region(levels):
    return AdministrativeUnit.objects.create(name="Béré", level=levels["region"])


@pytest.fixture
def commune(levels, region):
    return AdministrativeUnit.objects.create(name="Dabou", level=levels["commune"], parent=region)


@pytest.fixture
def other_commune(levels, region):
    return AdministrativeUnit.objects.create(name="Sikensi", level=levels["commune"], parent=region)


@pytest.fixture
def village(levels, commune):
    return AdministrativeUnit.objects.create(name="Séguéla", level=levels["village"], parent=commune)


@pytest.fixture
def worksite(village):
    return Worksite.objects.create(
        name="Forage F-07", village=village, location=Point(BASE_LNG, BASE_LAT, srid=4326)
    )


@pytest.fixture
def unmapped_worksite(village):
    return Worksite.objects.create(name="Latrines LP-5", village=village, location=None)


def make_user(username, role, **extra):
    extra.setdefault("onboarded_on", date(2026, 1, 1))
    user = User(email=f"{username}@example.test", full_name=username.title(), role=role, **extra)
    user.set_password("pw")
    user.full_clean(exclude=["password"])
    user.save()
    return user


@pytest.fixture
def sc(commune):
    return make_user("koffi", Role.SC, commune=commune)


@pytest.fixture
def other_sc(other_commune):
    return make_user("awa", Role.SC, commune=other_commune)


@pytest.fixture
def ft(sc, commune, worksite):
    user = make_user("ibrahim", Role.FT, supervisor=sc, commune=commune)
    WorksiteAssignment.objects.create(user=user, worksite=worksite, assigned_on=date(2026, 1, 1))
    return user


@pytest.fixture
def fc(sc, commune):
    return make_user("mariam", Role.FC, supervisor=sc, commune=commune)


@pytest.fixture
def rdp(db):
    return make_user("rdp", Role.RDP)


@pytest.fixture
def admin_user(db):
    return make_user("admin", Role.ADMIN)


@pytest.fixture
def regional(region):
    return make_user("fatou", Role.REGIONAL_SPECIALIST, region=region)


@pytest.fixture
def national(db):
    return make_user("konan", Role.NATIONAL_SPECIALIST)


@pytest.fixture
def client_for():
    def make(user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    return make


def jpeg(color=(120, 110, 90), size=(64, 48), pattern=0) -> SimpleUploadedFile:
    image = Image.new("RGB", size, color)
    if pattern:
        for x in range(0, size[0], 4):
            for y in range(size[1]):
                image.putpixel((x, y), ((x * pattern) % 255, (y * 7) % 255, 40))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    return SimpleUploadedFile("photo.jpg", buffer.getvalue(), content_type="image/jpeg")


@pytest.fixture
def capture(client_for):
    """Request a capture token and upload a photo with it, as the app does."""

    def run(user, upload=True, **photo_kwargs):
        client = client_for(user)
        token = client.post("/api/v1/photos/capture-token/").json()["token"]
        if upload:
            response = client.post(
                "/api/v1/photos/", {"capture_token": token, "file": jpeg(**photo_kwargs)},
                format="multipart",
            )
            assert response.status_code == 201, response.content
        return token

    return run


@pytest.fixture
def check_in(client_for, capture):
    def run(user, worksite, lat=BASE_LAT, lng=BASE_LNG, accuracy_m=12, **extra):
        token = extra.pop("capture_token", None) or capture(user)
        payload = {
            "worksite_id": str(worksite.id),
            "lat": lat,
            "lng": lng,
            "accuracy_m": accuracy_m,
            "capture_token": token,
            "is_mock_location": False,
            "idempotency_key": str(uuid.uuid4()),
            **extra,
        }
        return client_for(user).post("/api/v1/visits/check-in/", payload, format="json")

    return run


def utc(*args):
    from datetime import UTC

    return datetime(*args, tzinfo=UTC)


def days(n):
    return timedelta(days=n)
