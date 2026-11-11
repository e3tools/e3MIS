"""Attendance lists for events (Nov 2026, first used for the refugee symposium of 10-11 Nov).

Staff create an event and open it; anyone with its QR code signs the list from their phone, without
an account, once per day of the event. Closing the event closes the public page.
"""
import secrets

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


def new_token():
    return secrets.token_urlsafe(12)


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        OPEN = "open", _("Open")
        CLOSED = "closed", _("Closed")

    title = models.CharField(_("Title"), max_length=200)
    start_date = models.DateField(_("First day"))
    end_date = models.DateField(_("Last day"))
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)
    # In the public address, so the page cannot be found by guessing.
    token = models.CharField(max_length=32, unique=True, default=new_token, editable=False)
    # Poster: a band of logos on top and a background colour. Kept in the database (small, and no
    # media volume needed).
    banner = models.BinaryField(null=True, blank=True, editable=False)
    banner_type = models.CharField(max_length=32, blank=True, editable=False)
    poster_color = models.CharField(max_length=7, default="#ffffff")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date", "-id"]

    def __str__(self):
        return self.title

    def days(self):
        """Every day of the event, first to last."""
        from datetime import timedelta

        return [self.start_date + timedelta(days=n) for n in range((self.end_date - self.start_date).days + 1)]


class Attendance(models.Model):
    """One signature on the list, for one day of the event."""

    class Gender(models.TextChoices):
        FEMALE = "F", _("Female")
        MALE = "H", _("Male")
        UNSAID = "N", _("Prefer not to say")

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="attendances")
    day = models.DateField()
    # 1, 2, 3… for each day of the event, in signing order.
    number = models.PositiveIntegerField()
    full_name = models.CharField(max_length=200)
    # Required on the form; empty on the signatures made before it existed (10-11 Nov 2026),
    # counted like "prefer not to say".
    gender = models.CharField(_("Gender"), max_length=1, choices=Gender.choices, blank=True)
    organisation = models.CharField(max_length=200)
    position = models.CharField(max_length=200)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    # The phone's last digits, to recognise one number written in different ways.
    phone_key = models.CharField(max_length=20, blank=True)
    signature = models.BinaryField()
    language = models.CharField(max_length=8, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["day", "number"]
        constraints = [
            models.UniqueConstraint(fields=["event", "day", "number"], name="attendance_unique_number"),
            models.UniqueConstraint(
                fields=["event", "day", "email"], name="attendance_unique_email", condition=~models.Q(email=""),
            ),
            models.UniqueConstraint(
                fields=["event", "day", "phone_key"], name="attendance_unique_phone",
                condition=~models.Q(phone_key=""),
            ),
        ]

    def __str__(self):
        return f"{self.event} {self.day} #{self.number} {self.full_name}"
