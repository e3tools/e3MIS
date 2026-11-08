"""Event attendance lists (Nov 2026, refugee symposium of 10-11 Nov).

Anyone with the QR code signs from their phone, without an account, once per day; the public list
shows only the number, a shortened name and the organisation. Staff open and close the list and
export it (PDF with the signatures, Excel without).
"""
import base64
from datetime import date, timedelta
from io import BytesIO
from unittest import mock

import pytest
from django.urls import reverse
from openpyxl import load_workbook
from PIL import Image, ImageDraw

from authorization.models import CustomUser
from events import attendance as attendance_module
from events.models import Attendance, Event
from tests.conftest import client_for

DAY_ONE = date(2026, 11, 10)


def signature(blank=False):
    image = Image.new("RGBA", (600, 180), (0, 0, 0, 0))
    if not blank:
        ImageDraw.Draw(image).line([(20, 100), (200, 40), (380, 140)], fill=(0, 0, 0, 255), width=4)
    out = BytesIO()
    image.save(out, format="PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()


def form_data(**overrides):
    data = {
        "full_name": "BIO Awa Mariam", "organisation": "HCR", "position": "Chargée de protection",
        "country": "Bénin", "city": "Cotonou", "email": "awa@example.test", "phone": "+229 01 97 11 11 11",
        "signature": signature(), "website": "",
    }
    data.update(overrides)
    return data


@pytest.fixture
def event(db):
    return Event.objects.create(
        title="Symposium sur les réfugiés", start_date=DAY_ONE, end_date=DAY_ONE + timedelta(days=1),
        status=Event.Status.OPEN,
    )


@pytest.fixture
def on_day():
    """The server's date, for the event's days."""
    with mock.patch.object(attendance_module, "today", return_value=DAY_ONE) as patched:
        yield patched


def url(name, event, **query):
    path = reverse(f"events:{name}", kwargs={"token": event.token})
    return path + ("?" + "&".join(f"{k}={v}" for k, v in query.items()) if query else "")


# --- Public pages ------------------------------------------------------------------------------

def test_anyone_signs_without_an_account_and_gets_a_number(client, event, on_day):
    response = client.post(url("sign", event), form_data())
    assert response.status_code == 302 and response.url == url("thanks", event)
    page = client.get(response.url).content.decode()
    assert "N° 1" in page
    second = client.post(url("sign", event), form_data(email="moussa@example.test", phone="0197222222"))
    assert second.status_code == 302
    attendance = Attendance.objects.get(email="moussa@example.test")
    assert (attendance.day, attendance.number) == (DAY_ONE, 2)
    assert Image.open(BytesIO(bytes(attendance.signature))).format == "PNG"


def test_one_signature_per_person_and_day_by_email_or_phone(client, event, on_day):
    client.post(url("sign", event), form_data())
    # Same phone written another way, other email: recognised.
    client.post(url("sign", event), form_data(email="other@example.test", phone="0197111111"))
    assert Attendance.objects.count() == 1
    assert "Vous aviez déjà émargé aujourd’hui." in client.get(url("thanks", event)).content.decode()
    # The next day, the same person signs again, numbered from 1.
    on_day.return_value = DAY_ONE + timedelta(days=1)
    client.post(url("sign", event), form_data())
    assert list(Attendance.objects.values_list("day", "number")) == [(DAY_ONE, 1), (DAY_ONE + timedelta(days=1), 1)]


def test_the_form_requires_a_signature_and_a_contact(client, event, on_day):
    response = client.post(url("sign", event), form_data(email="", phone="", signature=signature(blank=True)))
    errors = response.context["form"].errors
    assert errors["signature"] == ["Signez dans le cadre."]
    assert errors["email"] == ["Indiquez un e-mail ou un numéro de téléphone (au moins un)."]
    response = client.post(url("sign", event), form_data(signature="data:image/png;base64,bm90IGFuIGltYWdl"))
    assert response.context["form"].errors["signature"] == ["La signature n’a pas pu être lue : signez à nouveau."]
    assert Attendance.objects.count() == 0


def test_robots_filling_the_hidden_field_are_ignored(client, event, on_day):
    client.post(url("sign", event), form_data(website="http://spam.example"))
    assert Attendance.objects.count() == 0


def test_signing_is_closed_outside_the_days_and_once_closed(client, event, on_day):
    on_day.return_value = DAY_ONE - timedelta(days=1)
    assert "sign-form" not in client.get(url("sign", event)).content.decode()
    client.post(url("sign", event), form_data())
    assert Attendance.objects.count() == 0

    on_day.return_value = DAY_ONE
    event.status = Event.Status.CLOSED
    event.save()
    page = client.get(url("sign", event)).content.decode()
    assert "La liste de présence de cet évènement est close." in page
    client.post(url("sign", event), form_data())
    assert Attendance.objects.count() == 0


def test_a_draft_event_has_no_public_page(client, event):
    event.status = Event.Status.DRAFT
    event.save()
    assert client.get(url("sign", event)).status_code == 404


def test_public_list_shows_number_short_name_and_organisation_only(client, event, on_day):
    client.post(url("sign", event), form_data())
    page = client.get(url("attendees", event)).content.decode()
    assert "BIO A. M." in page and "HCR" in page
    for private in ("Awa", "awa@example.test", "97 11 11 11", "Cotonou", "protection"):
        assert private not in page
    assert "1 participant" in page
    assert reverse("events:signature", kwargs={"pk": Attendance.objects.get().pk}) not in page


def test_have_i_signed_by_email_or_phone(client, event, on_day):
    client.post(url("sign", event), form_data())
    assert "N° 1" in client.get(url("check", event, contact="AWA@example.test")).content.decode()
    assert "N° 1" in client.get(url("check", event, contact="0197111111")).content.decode()
    page = client.get(url("check", event, contact="nobody@example.test")).content.decode()
    assert "Aucune signature trouvée" in page


def test_the_page_offers_english(client, event, on_day):
    page = client.get(url("sign", event)).content.decode()
    assert f'href="/en/e/{event.token}/"' in page
    english = client.get(f"/en/e/{event.token}/").content.decode()
    assert "Sign the list" in english


# --- Staff -------------------------------------------------------------------------------------

@pytest.fixture
def desk_user(db):
    return CustomUser.objects.create_user(email="desk@example.test", password="x")


def test_event_pages_and_files_are_for_django_admin_users_only(client, desk_user, staff_client, event, on_day):
    client.post(url("sign", event), form_data())
    pages = [
        reverse("events:list"), reverse("events:detail", kwargs={"pk": event.pk}),
        reverse("events:poster", kwargs={"pk": event.pk}),
        reverse("events:signature", kwargs={"pk": Attendance.objects.get().pk}),
    ] + [reverse("events:file", kwargs={"pk": event.pk, "kind": kind}) for kind in ("pdf", "xlsx", "blank", "qr")]
    for page in pages:
        assert client_for(desk_user).get(page).status_code == 403, page
        assert staff_client.get(page).status_code == 200, page
    assert client.get(pages[-1]).status_code == 302


def test_staff_create_then_open_an_event_and_only_one_is_open(staff_client, event):
    response = staff_client.post(reverse("events:list"), {
        "title": "Atelier", "start_date": "2026-12-01", "end_date": "2026-12-01",
    })
    new = Event.objects.get(title="Atelier")
    assert response.url == reverse("events:detail", kwargs={"pk": new.pk})
    assert new.status == Event.Status.DRAFT
    staff_client.post(response.url, {"action": "open"})
    event.refresh_from_db()
    new.refresh_from_db()
    assert (new.status, event.status) == (Event.Status.OPEN, Event.Status.CLOSED)
    staff_client.post(response.url, {"action": "close"})
    new.refresh_from_db()
    assert new.status == Event.Status.CLOSED


def test_exports_carry_the_list(staff_client, client, event, on_day):
    client.post(url("sign", event), form_data())
    pdf = staff_client.get(reverse("events:file", kwargs={"pk": event.pk, "kind": "pdf"}))
    assert pdf["Content-Type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    xlsx = staff_client.get(reverse("events:file", kwargs={"pk": event.pk, "kind": "xlsx"}))
    rows = list(load_workbook(BytesIO(xlsx.content)).active.iter_rows(values_only=True))
    assert rows[1][1:5] == (1, "BIO Awa Mariam", "HCR", "Chargée de protection")
    blank = staff_client.get(reverse("events:file", kwargs={"pk": event.pk, "kind": "blank"}))
    assert blank.content.startswith(b"%PDF")
    qr = staff_client.get(reverse("events:file", kwargs={"pk": event.pk, "kind": "qr"}))
    assert Image.open(BytesIO(qr.content)).format == "PNG"


def test_poster_with_a_logo_band_and_a_colour(staff_client, event):
    out = BytesIO()
    Image.new("RGB", (800, 120), (0, 80, 160)).save(out, format="PNG")
    out.name = "logos.png"
    out.seek(0)
    detail = reverse("events:detail", kwargs={"pk": event.pk})
    staff_client.post(detail, {"action": "poster", "poster_color": "#fdf6e3", "banner": out})
    event.refresh_from_db()
    assert (event.poster_color, event.banner_type) == ("#fdf6e3", "image/png")
    poster = staff_client.get(reverse("events:poster", kwargs={"pk": event.pk})).content.decode()
    assert "#fdf6e3" in poster and "<svg" in poster and event.token in poster
