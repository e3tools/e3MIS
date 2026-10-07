"""Trusted clock for visits recorded without signal (merge plan D2/Q7/Q8).

The phone never sends a wall-clock time (non-negotiable 2). While online it receives a
server-signed timestamp (the *anchor*) and notes its own monotonic uptime at that moment. When
it records a check-in or check-out offline, it sends the anchor back with the uptime then and
now, and its boot identifier both times. The server rebuilds the event time as

    event = anchor time (signed by this server) + (uptime now - uptime at the anchor)

The uptime counter keeps running while the phone sleeps and cannot be changed in the phone's
settings; a restart resets it, which the boot identifier detects. Anything that cannot be proven
(bad signature, restart, anchor too old, a time in the future) is ``unproven``: the server keeps
its own receipt time and the visit goes to a person (Q8). It never becomes "missed".
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.core import signing
from django.utils.dateparse import parse_datetime

from . import clock

SALT = "fieldmonitoring.trusted-clock.v1"
# Online requests arrive within seconds; below this gap the server's own receipt time is used.
ONLINE_GAP = timedelta(minutes=2)
# Network and processing delay tolerated between the derived time and the receipt time.
FUTURE_SLACK = timedelta(minutes=2)


class TimeSource:
    SERVER = "server"  # received online: the server's own clock
    PHONE_CLOCK = "phone_clock"  # recorded offline, proven by the trusted clock
    UNPROVEN = "unproven"  # recorded offline, could not be proven: server receipt time, review

    choices = [
        (SERVER, "Server time at receipt"),
        (PHONE_CLOCK, "Trusted clock (recorded offline)"),
        (UNPROVEN, "Unproven offline time"),
    ]


def issue_anchor() -> str:
    """A signed copy of the server time, for the phone to measure elapsed time from."""
    return signing.dumps(clock.now().isoformat(), salt=SALT)


@dataclass(frozen=True)
class EventTime:
    at: datetime  # when the event happened, as far as the server can prove
    received_at: datetime
    source: str


def resolve(evidence: dict | None, *, max_age: timedelta, queued_at: datetime | None = None) -> EventTime:
    """The time of an event from the phone's clock evidence, or the receipt time.

    ``queued_at`` is the phone's own note of when it queued the request. It is never used as a
    time (non-negotiable 2), only as a signal: a request that waited on the phone but carries no
    evidence (no anchor yet, or an app build without the trusted clock) cannot be dated, so it is
    unproven and goes to review rather than being taken as happening at receipt.
    """
    received = clock.now()
    if not evidence:
        if queued_at is not None and received - queued_at > ONLINE_GAP:
            return EventTime(received, received, TimeSource.UNPROVEN)
        return EventTime(received, received, TimeSource.SERVER)
    derived = _derive(evidence, max_age=max_age)
    if derived is None or derived > received + FUTURE_SLACK:
        return EventTime(received, received, TimeSource.UNPROVEN)
    if received - derived <= ONLINE_GAP:
        return EventTime(received, received, TimeSource.SERVER)
    return EventTime(derived, received, TimeSource.PHONE_CLOCK)


def _derive(evidence: dict, *, max_age: timedelta) -> datetime | None:
    try:
        anchor = parse_datetime(signing.loads(evidence["anchor"], salt=SALT))
        elapsed_ms = int(evidence["elapsed_ms"]) - int(evidence["anchor_elapsed_ms"])
        same_boot = str(evidence["boot_id"]) == str(evidence["anchor_boot_id"])
    except (KeyError, TypeError, ValueError, signing.BadSignature):
        return None
    if anchor is None or not same_boot or elapsed_ms < 0:
        return None
    if timedelta(milliseconds=elapsed_ms) > max_age:
        return None
    return anchor + timedelta(milliseconds=elapsed_ms)
