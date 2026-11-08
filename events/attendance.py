"""Signing an event's list: the day, the numbering, the signature image and what the public sees."""
import base64
import binascii
import re
from io import BytesIO

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.utils import timezone
from django.utils.translation import gettext as _
from PIL import Image, UnidentifiedImageError

from events.models import Attendance, Event

SIGNATURE_MAX_BYTES = 400 * 1024
SIGNATURE_PREFIX = "data:image/png;base64,"
PHONE_KEY_DIGITS = 9


def today():
    """The programme's date (server clock), not the phone's."""
    from fieldmonitoring.core.models import ProgrammeConfig

    return timezone.localtime(timezone.now(), ProgrammeConfig.get().tz).date()


def is_signing_day(event):
    return event.status == Event.Status.OPEN and event.start_date <= today() <= event.end_date


def phone_key(phone):
    """The last digits: "+229 01 97 11 11 11" and "0197111111" are the same number."""
    return re.sub(r"\D", "", phone or "")[-PHONE_KEY_DIGITS:]


def public_name(full_name):
    """What the public list shows: the first word and the initials of the others ("BIO A.")."""
    words = full_name.split()
    if not words:
        return ""
    return " ".join([words[0]] + [f"{word[0].upper()}." for word in words[1:]])


def signature_png(data_url):
    """The signature drawn on the page (a PNG data URL), checked and re-encoded; ValidationError
    when missing, not an image or blank."""
    if not data_url or not data_url.startswith(SIGNATURE_PREFIX):
        raise ValidationError(_("Sign in the box."))
    try:
        raw = base64.b64decode(data_url[len(SIGNATURE_PREFIX):], validate=True)
    except (binascii.Error, ValueError):
        raise ValidationError(_("The signature could not be read: sign again."))
    if len(raw) > SIGNATURE_MAX_BYTES:
        raise ValidationError(_("The signature could not be read: sign again."))
    try:
        image = Image.open(BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError(_("The signature could not be read: sign again."))
    if image.width > 3000 or image.height > 1500:
        raise ValidationError(_("The signature could not be read: sign again."))
    image = image.convert("RGBA")
    if image.getchannel("A").getbbox() is None:
        raise ValidationError(_("Sign in the box."))
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def already_signed(event, day, email="", phone=""):
    """The signature of this email or phone on that day, if any."""
    conditions = Q()
    if email:
        conditions |= Q(email__iexact=email)
    if phone_key(phone):
        conditions |= Q(phone_key=phone_key(phone))
    if not conditions:
        return None
    return event.attendances.filter(conditions, day=day).first()


def sign(event, data, signature, language=""):
    """Adds a signature for today, numbered after the day's last one. Returns the Attendance, or
    the earlier one of this email or phone (``created`` False)."""
    day = today()
    with transaction.atomic():
        # One signer numbers at a time.
        Event.objects.select_for_update().get(pk=event.pk)
        earlier = already_signed(event, day, data["email"], data["phone"])
        if earlier:
            return earlier, False
        last = event.attendances.filter(day=day).aggregate(last=Max("number"))["last"] or 0
        try:
            with transaction.atomic():
                attendance = Attendance.objects.create(
                    event=event, day=day, number=last + 1, signature=signature, language=language,
                    full_name=data["full_name"], organisation=data["organisation"], position=data["position"],
                    country=data["country"], city=data["city"], email=data["email"].lower(),
                    phone=data["phone"], phone_key=phone_key(data["phone"]),
                )
        except IntegrityError:
            return already_signed(event, day, data["email"], data["phone"]), False
    return attendance, True


def find(event, contact):
    """The signatures of an email or a phone number, every day."""
    contact = contact.strip()
    if "@" in contact:
        return list(event.attendances.filter(email__iexact=contact))
    key = phone_key(contact)
    if len(key) < 6:
        return []
    return list(event.attendances.filter(phone_key=key))
