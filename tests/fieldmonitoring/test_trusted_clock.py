"""Trusted clock for visits recorded offline (merge plan D2, Q7, Q8; non-negotiables 1 and 2).

The phone sends no wall-clock time: only a server-signed anchor and its monotonic uptime at the
anchor and at the event. A time the phone cannot prove keeps the server's receipt time and goes
to a person, never to "missed".
"""

from datetime import timedelta

import pytest
import time_machine
from django.core import signing

from fieldmonitoring.core import trusted_clock
from fieldmonitoring.core.trusted_clock import TimeSource
from fieldmonitoring.visits.models import Visit, VisitState
from tests.fieldmonitoring.conftest import utc

pytestmark = pytest.mark.django_db

MAX_AGE = timedelta(hours=72)


def anchor_at(when):
    with time_machine.travel(when, tick=False):
        return trusted_clock.issue_anchor()


def evidence(anchor, elapsed_s, *, boot="b1", anchor_boot="b1", anchor_elapsed_ms=10_000):
    return {
        "anchor": anchor,
        "anchor_elapsed_ms": anchor_elapsed_ms,
        "elapsed_ms": anchor_elapsed_ms + int(elapsed_s * 1000),
        "anchor_boot_id": anchor_boot,
        "boot_id": boot,
    }


def resolve_at(received, ev):
    with time_machine.travel(received, tick=False):
        return trusted_clock.resolve(ev, max_age=MAX_AGE)


def test_no_evidence_is_server_time():
    when = resolve_at(utc(2026, 10, 7, 9), None)
    assert when.source == TimeSource.SERVER and when.at == utc(2026, 10, 7, 9)


def test_offline_event_time_is_anchor_plus_elapsed():
    # Anchor at 08:00, visit 1 h later (09:00), synced at 17:00.
    when = resolve_at(utc(2026, 10, 7, 17), evidence(anchor_at(utc(2026, 10, 7, 8)), 3600))
    assert when.source == TimeSource.PHONE_CLOCK
    assert when.at == utc(2026, 10, 7, 9)
    assert when.received_at == utc(2026, 10, 7, 17)


def test_online_event_keeps_the_receipt_time():
    when = resolve_at(utc(2026, 10, 7, 9, 0, 30), evidence(anchor_at(utc(2026, 10, 7, 9)), 20))
    assert when.source == TimeSource.SERVER and when.at == utc(2026, 10, 7, 9, 0, 30)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda e: {**e, "boot_id": "b2"}, id="phone restarted"),
        pytest.param(lambda e: {**e, "elapsed_ms": e["anchor_elapsed_ms"] - 1}, id="uptime went back"),
        pytest.param(lambda e: {**e, "anchor": e["anchor"][:-2] + "xx"}, id="forged anchor"),
        pytest.param(lambda e: {**e, "anchor": signing.dumps("2026-10-07T06:00:00+00:00")}, id="wrong signer"),
        pytest.param(lambda e: {k: v for k, v in e.items() if k != "boot_id"}, id="incomplete"),
    ],
)
def test_unprovable_evidence_keeps_receipt_time(mutate):
    ev = mutate(evidence(anchor_at(utc(2026, 10, 7, 8)), 3600))
    when = resolve_at(utc(2026, 10, 7, 17), ev)
    assert when.source == TimeSource.UNPROVEN and when.at == utc(2026, 10, 7, 17)


def test_event_in_the_future_is_unproven():
    when = resolve_at(utc(2026, 10, 7, 9), evidence(anchor_at(utc(2026, 10, 7, 8)), 2 * 3600))
    assert when.source == TimeSource.UNPROVEN


def test_offline_longer_than_allowed_is_unproven():
    when = resolve_at(utc(2026, 10, 12, 9), evidence(anchor_at(utc(2026, 10, 7, 8)), 73 * 3600))
    assert when.source == TimeSource.UNPROVEN


def test_health_returns_a_signed_anchor(client):
    with time_machine.travel(utc(2026, 10, 7, 8), tick=False):
        body = client.get("/api/v1/health/").json()
    assert signing.loads(body["clock_anchor"], salt=trusted_clock.SALT).startswith("2026-10-07T08:00")


# --- Visits recorded offline ----------------------------------------------------------------


def offline_visit(ft, worksite, check_in, client_for, *, checkout_ev):
    anchor = anchor_at(utc(2026, 10, 7, 8))
    with time_machine.travel(utc(2026, 10, 7, 17), tick=False):
        visit_id = check_in(ft, worksite, clock=evidence(anchor, 3600)).json()["id"]
        body = client_for(ft).post(
            f"/api/v1/visits/{visit_id}/check-out/",
            {"idempotency_key": "out", "clock": checkout_ev(anchor)},
            format="json",
        ).json()
    return body


def test_offline_visit_is_dated_when_it_happened_and_verified(ft, worksite, check_in, client_for):
    body = offline_visit(ft, worksite, check_in, client_for, checkout_ev=lambda a: evidence(a, 3600 + 45 * 60))
    assert body["state"] == "verified"
    assert body["checked_in_at"].startswith("2026-10-07T09:00")
    assert body["checked_out_at"].startswith("2026-10-07T09:45")
    assert body["time_on_site_s"] == 45 * 60
    assert body["checkin_time_source"] == "phone_clock" and body["checkout_time_source"] == "phone_clock"
    assert body["checkin_received_at"].startswith("2026-10-07T17:00")
    assert body["short_visit"] is False


def test_unproven_check_in_goes_to_review_not_missed(ft, worksite, check_in):
    anchor = anchor_at(utc(2026, 10, 7, 8))
    with time_machine.travel(utc(2026, 10, 7, 17), tick=False):
        body = check_in(ft, worksite, clock=evidence(anchor, 3600, boot="b2")).json()
    assert body["state"] == "unverified" and body["unverified_reason"] == "time_unproven"
    assert body["checked_in_at"].startswith("2026-10-07T17:00")
    assert Visit.objects.get(pk=body["id"]).state != VisitState.MISSED


def test_unproven_check_out_goes_to_review(ft, worksite, check_in, client_for):
    body = offline_visit(ft, worksite, check_in, client_for, checkout_ev=lambda a: evidence(a, 3600 + 600, boot="b2"))
    assert body["state"] == "unverified" and body["unverified_reason"] == "time_unproven"
    assert body["checkout_time_source"] == "unproven"


def test_check_out_before_check_in_is_unproven(ft, worksite, check_in, client_for):
    body = offline_visit(ft, worksite, check_in, client_for, checkout_ev=lambda a: evidence(a, 1800))
    assert body["unverified_reason"] == "time_unproven"


def test_failed_location_keeps_its_reason_over_time(ft, worksite, check_in):
    from tests.fieldmonitoring.conftest import BASE_LAT, BASE_LNG, north_of

    lat, lng = north_of(BASE_LAT, BASE_LNG, 500)
    anchor = anchor_at(utc(2026, 10, 7, 8))
    with time_machine.travel(utc(2026, 10, 7, 17), tick=False):
        body = check_in(ft, worksite, lat=lat, lng=lng, clock=evidence(anchor, 3600, boot="b2")).json()
    assert body["unverified_reason"] == "location_failed"


def test_client_wall_clock_is_still_ignored(ft, worksite, check_in):
    # Non-negotiable 2: a client timestamp field is never used.
    with time_machine.travel(utc(2026, 10, 7, 17), tick=False):
        body = check_in(ft, worksite, checked_in_at="2026-10-07T06:00:00Z").json()
    assert body["checked_in_at"].startswith("2026-10-07T17:00")
    assert body["checkin_time_source"] == "server"


def test_queued_without_evidence_is_unproven_not_dated_at_receipt(ft, worksite, check_in):
    # A phone with no anchor yet (or an older build) queued the check-in at 09:00; it arrives at 17:00.
    with time_machine.travel(utc(2026, 10, 7, 17), tick=False):
        body = check_in(ft, worksite, client_captured_at="2026-10-07T09:00:00Z").json()
    assert body["state"] == "unverified" and body["unverified_reason"] == "time_unproven"
    assert body["checkin_time_source"] == "unproven"


def test_online_check_in_with_capture_time_is_server_time(ft, worksite, check_in):
    with time_machine.travel(utc(2026, 10, 7, 17), tick=False):
        body = check_in(ft, worksite, client_captured_at="2026-10-07T16:59:30Z").json()
    assert body["checkin_time_source"] == "server" and body["state"] == "in_progress"


def test_queued_check_out_without_evidence_goes_to_review(ft, worksite, check_in, client_for):
    with time_machine.travel(utc(2026, 10, 7, 9), tick=False):
        visit_id = check_in(ft, worksite).json()["id"]
    with time_machine.travel(utc(2026, 10, 7, 17), tick=False):
        body = client_for(ft).post(
            f"/api/v1/visits/{visit_id}/check-out/",
            {"idempotency_key": "out", "client_captured_at": "2026-10-07T09:40:00Z"},
            format="json",
        ).json()
    assert body["unverified_reason"] == "time_unproven"
