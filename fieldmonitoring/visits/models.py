import uuid

from django.conf import settings
from django.contrib.gis.db import models
from django.db.models import Q

from fieldmonitoring.core.models import UUIDModel
from fieldmonitoring.core.trusted_clock import TimeSource


class VisitState(models.TextChoices):
    # `in_progress` is the IN PROGRESS box of the state machine in
    # spec/docs/03-domain-model.md: checked in with passing checks, not yet checked out.
    IN_PROGRESS = "in_progress", "In progress"
    VERIFIED = "verified", "Verified"
    UNVERIFIED = "unverified", "Unverified"
    MISSED = "missed", "Missed"


class UnverifiedReason(models.TextChoices):
    LOCATION_FAILED = "location_failed", "Location check failed"
    NO_CHECKOUT = "no_checkout", "No check-out"
    MOCK_LOCATION = "mock_location", "Mock location"
    NO_COORDINATE = "no_coordinate", "Worksite has no coordinate"
    # Extension: checked out, but the queued arrival photo never reached the server.
    NO_PHOTO = "no_photo", "Arrival photo not received"
    # Recorded offline and the phone could not prove when (trusted clock, merge plan Q8).
    TIME_UNPROVEN = "time_unproven", "Offline time could not be proven"


class FieldReasonCode(models.TextChoices):
    BATTERY_DIED = "battery_died", "Phone battery died"
    NO_NETWORK = "no_network", "No network"
    FORGOT = "forgot", "Forgot to check out"
    APP_CLOSED = "app_closed", "App closed"
    NO_LOCATION_FIX = "no_location_fix", "Could not get a location fix"
    OTHER = "other", "Other"


class Photo(UUIDModel):
    file = models.ImageField(upload_to="photos/%Y/%m/")
    size_bytes = models.PositiveIntegerField()
    perceptual_hash = models.CharField(max_length=16, db_index=True)
    # Server-recorded receipt time.
    captured_at = models.DateTimeField(auto_now_add=True)
    exif_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    exif_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")


class CaptureToken(models.Model):
    """Issued before the camera opens; an upload without a valid unused token is rejected (BR-11)."""

    token = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    photo = models.OneToOneField(
        Photo, null=True, blank=True, on_delete=models.SET_NULL, related_name="capture_token"
    )


class Visit(UUIDModel):
    """One check-in / check-out pair, one worksite, one user."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="visits")
    worksite = models.ForeignKey(
        "registry.Worksite", on_delete=models.PROTECT, related_name="visits"
    )
    state = models.CharField(max_length=16, choices=VisitState.choices)
    unverified_reason = models.CharField(
        max_length=32, choices=UnverifiedReason.choices, null=True, blank=True
    )
    # When it happened, by the server's clock: the receipt time, or for a visit recorded offline
    # the time proven by the trusted clock (fieldmonitoring/core/trusted_clock.py). Never the
    # phone's wall clock (CLAUDE.md non-negotiable 2).
    checked_in_at = models.DateTimeField(db_index=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    checkin_received_at = models.DateTimeField(null=True, blank=True)
    checkout_received_at = models.DateTimeField(null=True, blank=True)
    checkin_time_source = models.CharField(max_length=16, choices=TimeSource.choices, default=TimeSource.SERVER)
    checkout_time_source = models.CharField(max_length=16, choices=TimeSource.choices, null=True, blank=True)
    time_on_site_s = models.PositiveIntegerField(null=True, blank=True)
    checkin_location = models.PointField(geography=True, srid=4326, null=True, blank=True)
    checkin_accuracy_m = models.PositiveIntegerField(null=True, blank=True)
    checkin_distance_m = models.PositiveIntegerField(null=True, blank=True)
    checkout_location = models.PointField(geography=True, srid=4326, null=True, blank=True)
    checkout_accuracy_m = models.PositiveIntegerField(null=True, blank=True)
    is_mock_location = models.BooleanField(default=False)
    capture_token = models.OneToOneField(
        CaptureToken, null=True, blank=True, on_delete=models.SET_NULL, related_name="visit"
    )
    photo = models.ForeignKey(Photo, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    auto_closed = models.BooleanField(default=False)
    field_reason_code = models.CharField(
        max_length=32, choices=FieldReasonCode.choices, null=True, blank=True
    )
    field_reason = models.TextField(null=True, blank=True)
    field_reason_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(null=True, blank=True)
    # Metadata from a queued submission (Story 2.7). Never used for any rule.
    client_captured_at = models.DateTimeField(null=True, blank=True)
    checkin_idempotency_key = models.CharField(max_length=64)
    checkout_idempotency_key = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        ordering = ["-checked_in_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "checkin_idempotency_key"], name="unique_checkin_idempotency"
            ),
            # unverified_reason is set whenever state is unverified and null otherwise (Story 3.1).
            models.CheckConstraint(
                condition=(Q(state="unverified") & Q(unverified_reason__isnull=False))
                | (~Q(state="unverified") & Q(unverified_reason__isnull=True)),
                name="unverified_reason_matches_state",
            ),
            # No automated path reaches `missed`: it always carries a human actor.
            models.CheckConstraint(
                condition=~Q(state="missed") | Q(resolved_by__isnull=False),
                name="missed_requires_resolver",
            ),
        ]

    @property
    def awaiting_review(self) -> bool:
        return self.state == VisitState.UNVERIFIED and self.resolved_by_id is None


def is_short_visit(visit, threshold_s: int) -> bool:
    """Checked out, with less than ``threshold_s`` seconds on site. Auto-closed visits have no time on site."""
    return visit.checked_out_at is not None and visit.time_on_site_s is not None and visit.time_on_site_s < threshold_s


class WorksProgress(models.TextChoices):
    ON_SCHEDULE = "on_schedule", "On schedule"
    MINOR_DELAY = "minor_delay", "Minor delay"
    STOPPED = "stopped", "Stopped"


class VisitStatus(models.Model):
    """Programme content captured during the visit. Three fields only (Story 2.5)."""

    visit = models.OneToOneField(Visit, primary_key=True, on_delete=models.CASCADE, related_name="status")
    works_progress = models.CharField(max_length=16, choices=WorksProgress.choices)
    # Any problem at the worksite since the last visit. Not a grievance channel:
    # grievances are handled outside this app.
    issue_reported = models.BooleanField()
    # What the problem is, when one is reported. Required by the app from build 13; optional here so
    # older builds, which never send it, keep working.
    issue_description = models.TextField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)


class FlagKind(models.TextChoices):
    MOCK_LOCATION = "mock_location", "Mock location"
    IMPOSSIBLE_TRAVEL = "impossible_travel", "Impossible travel"
    PHOTO_REUSE = "photo_reuse", "Photo reuse"
    ROTATION_REPEAT = "rotation_repeat", "Rotation repeat"


class VisitFlag(UUIDModel):
    """Information for a reviewer. Only mock_location changes state, and it does so at check-in."""

    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="flags")
    kind = models.CharField(max_length=32, choices=FlagKind.choices)
    detail = models.JSONField(default=dict)
    raised_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["raised_at"]


class AppendOnlyError(Exception):
    pass


class VisitEvent(UUIDModel):
    """Immutable audit trail: every state change appends one row (Story 3.5)."""

    visit = models.ForeignKey(Visit, on_delete=models.PROTECT, related_name="events")
    event = models.CharField(max_length=32)
    from_state = models.CharField(max_length=16, null=True, blank=True)
    to_state = models.CharField(max_length=16)
    reason = models.CharField(max_length=32, null=True, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["at"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AppendOnlyError("Visit events are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyError("Visit events are append-only.")
