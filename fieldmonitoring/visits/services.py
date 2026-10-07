"""Visit capture (Epic 2) and the automated parts of verification (Epic 3)."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from PIL import Image, UnidentifiedImageError

from authorization.models import SPECIALIST_ROLES
from fieldmonitoring.compliance import rules
from fieldmonitoring.core import clock, trusted_clock
from fieldmonitoring.core.trusted_clock import TimeSource
from fieldmonitoring.core.models import ProgrammeConfig
from fieldmonitoring.registry.models import ProvisionalCoordinate, Worksite

from . import photos
from .models import (
    CaptureToken,
    FlagKind,
    Photo,
    UnverifiedReason,
    Visit,
    VisitFlag,
    VisitState,
    VisitStatus,
)
from .state_machine import Event, apply


class VisitError(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


def make_point(lat, lng) -> Point | None:
    if lat is None or lng is None:
        return None
    return Point(float(lng), float(lat), srid=4326)


def distance_m(a: Point, b: Point) -> float:
    """Great-circle distance in metres, computed by PostGIS on geography."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ST_Distance(ST_GeogFromWKB(%s), ST_GeogFromWKB(%s))",
            [bytes(a.wkb), bytes(b.wkb)],
        )
        return float(cursor.fetchone()[0])


# --- Photos (Story 2.4, BR-11) ------------------------------------------------------


def issue_capture_token(user) -> CaptureToken:
    ttl = ProgrammeConfig.get().capture_token_ttl_minutes
    return CaptureToken.objects.create(user=user, expires_at=clock.now() + timedelta(minutes=ttl))


@transaction.atomic
def upload_photo(user, token_id, file) -> Photo:
    try:
        token = CaptureToken.objects.select_for_update().get(token=token_id, user=user)
    except (CaptureToken.DoesNotExist, ValidationError, ValueError):
        raise VisitError("invalid_capture_token")
    if token.photo_id:
        raise VisitError("capture_token_used")
    visit = Visit.objects.filter(capture_token=token).first()
    # A token claimed by a check-in stays valid for its queued photo; otherwise it expires.
    if visit is None and clock.now() > token.expires_at:
        raise VisitError("capture_token_expired")
    if file.size > photos.MAX_PHOTO_BYTES:
        raise VisitError("photo_too_large")
    try:
        image = Image.open(file)
        image.load()
    except (UnidentifiedImageError, OSError):
        raise VisitError("invalid_image")

    exif = photos.exif_position(image)
    file.seek(0)
    photo = Photo.objects.create(
        file=file,
        size_bytes=file.size,
        perceptual_hash=photos.dhash(image),
        exif_lat=exif[0] if exif else None,
        exif_lng=exif[1] if exif else None,
        uploaded_by=user,
    )
    token.photo = photo
    token.save(update_fields=["photo"])
    if visit is not None:
        _attach_photo(visit, photo)
    return photo


def _attach_photo(visit: Visit, photo: Photo):
    visit.photo = photo
    apply(visit, Event.PHOTO_ATTACHED)
    _raise_photo_flags(visit, photo)


def _raise_photo_flags(visit: Visit, photo: Photo):
    """BR-11: reuse and EXIF mismatch are flags only; they never change state."""
    config = ProgrammeConfig.get()
    since = clock.now() - timedelta(days=config.photo_reuse_window_days)
    candidates = (
        Photo.objects.exclude(pk=photo.pk)
        .filter(capture_token__visit__isnull=False)
        .select_related("capture_token__visit")
    )
    same_user = candidates.filter(uploaded_by=visit.user)
    same_site = candidates.filter(
        capture_token__visit__worksite=visit.worksite, captured_at__gte=since
    )
    matches = []
    for other in (same_user | same_site).distinct():
        distance = photos.hamming(photo.perceptual_hash, other.perceptual_hash)
        if distance <= config.photo_hash_max_distance:
            matches.append(
                {"visit_id": str(other.capture_token.visit.id), "hash_distance": distance}
            )
    if matches:
        VisitFlag.objects.create(visit=visit, kind=FlagKind.PHOTO_REUSE, detail={"matches": matches})

    if photo.exif_lat is not None and visit.checkin_location is not None:
        exif_point = make_point(photo.exif_lat, photo.exif_lng)
        gap = distance_m(exif_point, visit.checkin_location)
        if gap > visit.worksite.tolerance_m:
            VisitFlag.objects.create(
                visit=visit,
                kind=FlagKind.PHOTO_REUSE,
                detail={"type": "exif_mismatch", "distance_m": round(gap)},
            )


# --- Check-in (Story 2.3, BR-9, BR-12, BR-13, BR-7) --------------------------------


@dataclass
class CheckIn:
    worksite: Worksite
    lat: float | None
    lng: float | None
    accuracy_m: float | None
    capture_token: object
    is_mock_location: bool
    idempotency_key: str
    client_captured_at: datetime | None = None
    # Trusted-clock evidence from a phone that recorded the arrival offline (core/trusted_clock.py).
    clock: dict | None = None


def check_in(user, data: CheckIn) -> tuple[Visit, bool]:
    """Record an arrival. A failed check never blocks it. Returns (visit, created)."""
    existing = Visit.objects.filter(user=user, checkin_idempotency_key=data.idempotency_key).first()
    if existing:
        return existing, False
    try:
        with transaction.atomic():
            return _check_in(user, data), True
    except IntegrityError:
        # A concurrent retry with the same key won the race.
        return Visit.objects.get(user=user, checkin_idempotency_key=data.idempotency_key), False


def _check_in(user, data: CheckIn) -> Visit:
    config = ProgrammeConfig.get()
    worksite = data.worksite
    try:
        token = CaptureToken.objects.select_for_update().get(token=data.capture_token, user=user)
    except (CaptureToken.DoesNotExist, ValidationError, ValueError):
        raise VisitError("invalid_capture_token")
    if Visit.objects.filter(capture_token=token).exists():
        raise VisitError("capture_token_used")

    point = make_point(data.lat, data.lng)
    distance = distance_m(point, worksite.location) if point and worksite.location else None
    reason = rules.location_check(
        is_mock=data.is_mock_location,
        has_position=point is not None,
        worksite_has_coordinate=worksite.location is not None,
        accuracy_m=data.accuracy_m,
        distance_m=distance,
        tolerance_m=worksite.tolerance_m,
        max_accuracy_m=config.max_accuracy_m,
    )
    when = trusted_clock.resolve(data.clock, max_age=timedelta(hours=config.max_offline_hours))
    if when.source == TimeSource.UNPROVEN and not reason:
        reason = UnverifiedReason.TIME_UNPROVEN

    visit = Visit(
        user=user,
        worksite=worksite,
        # The server's receipt time, or the time proven by the trusted clock. Never the phone's own clock.
        checked_in_at=when.at,
        checkin_received_at=when.received_at,
        checkin_time_source=when.source,
        checkin_location=point,
        checkin_accuracy_m=round(data.accuracy_m) if data.accuracy_m is not None else None,
        checkin_distance_m=round(distance) if distance is not None else None,
        is_mock_location=data.is_mock_location,
        capture_token=token,
        photo=token.photo,
        checkin_idempotency_key=data.idempotency_key,
        client_captured_at=data.client_captured_at,
    )
    if reason:
        apply(visit, Event.CHECK_IN_FAILED, reason=UnverifiedReason(reason))
    else:
        apply(visit, Event.CHECK_IN_PASSED)

    if reason == UnverifiedReason.NO_COORDINATE and point is not None:
        # BR-9: captured provisionally; an admin must confirm before it becomes the geofence.
        ProvisionalCoordinate.objects.create(
            worksite=worksite,
            location=point,
            accuracy_m=visit.checkin_accuracy_m,
            captured_by=user,
            visit=visit,
        )
    if data.is_mock_location:
        VisitFlag.objects.create(
            visit=visit,
            kind=FlagKind.MOCK_LOCATION,
            detail={"device_class": user.device_class},
        )
    _check_impossible_travel(visit, config)
    _check_rotation(visit, config)
    if visit.photo_id:
        _raise_photo_flags(visit, visit.photo)
    return visit


def _check_impossible_travel(visit: Visit, config: ProgrammeConfig):
    """BR-13: implied speed from the previous check-in. A flag only."""
    if visit.checkin_location is None:
        return
    previous = (
        Visit.objects.filter(user=visit.user, checkin_location__isnull=False)
        .exclude(pk=visit.pk)
        .filter(checked_in_at__lte=visit.checked_in_at)
        .order_by("-checked_in_at")
        .first()
    )
    if previous is None:
        return
    meters = distance_m(previous.checkin_location, visit.checkin_location)
    seconds = (visit.checked_in_at - previous.checked_in_at).total_seconds()
    if rules.impossible_travel(meters, seconds, config.impossible_travel_kmh):
        speed = rules.implied_speed_kmh(meters, seconds)
        VisitFlag.objects.create(
            visit=visit,
            kind=FlagKind.IMPOSSIBLE_TRAVEL,
            detail={
                "previous_visit_id": str(previous.id),
                "distance_m": round(meters),
                "seconds": round(seconds),
                "speed_kmh": None if speed == float("inf") else round(speed),
            },
        )


def earlier_verified_days(user, worksite, before: datetime, tz) -> list:
    return [
        clock.local_date(dt)
        for dt in Visit.objects.filter(
            user=user, worksite=worksite, state=VisitState.VERIFIED, checked_in_at__lt=before
        ).values_list("checked_in_at", flat=True)
    ]


def _check_rotation(visit: Visit, config: ProgrammeConfig):
    """BR-7: reported, never blocking, never changing state."""
    if visit.user.role not in SPECIALIST_ROLES:
        return
    earlier = rules.rotation_repeat(
        visit.user.role,
        visit.worksite.is_high_risk,
        clock.local_date(visit.checked_in_at, config),
        earlier_verified_days(visit.user, visit.worksite, visit.checked_in_at, config.tz),
        config.rotation_window_days,
    )
    if earlier:
        VisitFlag.objects.create(
            visit=visit,
            kind=FlagKind.ROTATION_REPEAT,
            detail={"previous_visit_on": earlier.isoformat()},
        )


# --- Status, check-out, reason (Stories 2.5, 2.6, 2.8) -------------------------------


def submit_status(
    visit: Visit,
    *,
    works_progress: str,
    issue_reported: bool,
    issue_description: str | None = None,
    note: str | None = None,
):
    if visit.checked_out_at or visit.auto_closed:
        raise VisitError("visit_closed")
    VisitStatus.objects.update_or_create(
        visit=visit,
        defaults={
            "works_progress": works_progress,
            "issue_reported": issue_reported,
            "issue_description": issue_description if issue_reported else None,
            "note": note,
        },
    )


@transaction.atomic
def check_out(visit: Visit, *, idempotency_key: str, lat=None, lng=None, accuracy_m=None, clock=None) -> Visit:
    visit = Visit.objects.select_for_update().get(pk=visit.pk)
    if visit.checked_out_at is not None:
        return visit  # a retry; the first check-out stands
    if visit.auto_closed or visit.state not in (VisitState.IN_PROGRESS, VisitState.UNVERIFIED):
        raise VisitError("visit_closed")
    config = ProgrammeConfig.get()
    when = trusted_clock.resolve(clock, max_age=timedelta(hours=config.max_offline_hours))
    unproven = when.source == TimeSource.UNPROVEN or when.at < visit.checked_in_at
    visit.checked_out_at = when.received_at if unproven else when.at
    visit.checkout_received_at = when.received_at
    visit.checkout_time_source = TimeSource.UNPROVEN if unproven else when.source
    visit.time_on_site_s = max(0, int((visit.checked_out_at - visit.checked_in_at).total_seconds()))
    visit.checkout_location = make_point(lat, lng)
    visit.checkout_accuracy_m = round(accuracy_m) if accuracy_m is not None else None
    visit.checkout_idempotency_key = idempotency_key
    return apply(visit, Event.CHECK_OUT, time_unproven=unproven)


def submit_reason(visit: Visit, *, code: str, note: str | None) -> Visit:
    if not visit.awaiting_review:
        raise VisitError("not_awaiting_review")
    visit.field_reason_code = code
    visit.field_reason = note
    visit.field_reason_at = clock.now()
    visit.save(update_fields=["field_reason_code", "field_reason", "field_reason_at"])
    return visit


# --- Auto-close (BR-8, Story 3.2) ----------------------------------------------------


def auto_close(cutoff: datetime) -> int:
    """Close visits checked in at or before `cutoff` that are still open. Idempotent."""
    open_visits = Visit.objects.filter(checked_in_at__lte=cutoff, auto_closed=False).filter(
        # No check-out yet, or checked out but still waiting for the arrival photo.
        Q(checked_out_at__isnull=True, state__in=[VisitState.IN_PROGRESS, VisitState.UNVERIFIED])
        | Q(state=VisitState.IN_PROGRESS)
    )
    count = 0
    for visit in open_visits:
        with transaction.atomic():
            apply(visit, Event.AUTO_CLOSE)
        count += 1
    return count
