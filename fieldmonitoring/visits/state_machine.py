"""The visit state machine. Every visit state change in the system goes through `apply`.

See the diagram in spec/docs/03-domain-model.md and Story 3.1.

Invariant: no automated event reaches MISSED. Only RESOLVE_* events carry a human
actor, and they are the only transitions out of UNVERIFIED. `transition` refuses a
MISSED target without an actor, and the database enforces it again with a check
constraint on Visit.
"""

from dataclasses import dataclass
from enum import StrEnum

from fieldmonitoring.core import clock

from .models import UnverifiedReason, Visit, VisitEvent, VisitState

S = VisitState


class Event(StrEnum):
    CHECK_IN_PASSED = "check_in_passed"
    CHECK_IN_FAILED = "check_in_failed"
    CHECK_OUT = "check_out"
    PHOTO_ATTACHED = "photo_attached"
    AUTO_CLOSE = "auto_close"
    RESOLVE_VERIFIED = "resolve_verified"
    RESOLVE_MISSED = "resolve_missed"


HUMAN_EVENTS = frozenset({Event.RESOLVE_VERIFIED, Event.RESOLVE_MISSED})
AUTOMATED_EVENTS = frozenset(Event) - HUMAN_EVENTS


class InvalidTransition(Exception):
    pass


@dataclass(frozen=True)
class Outcome:
    state: VisitState
    reason: UnverifiedReason | None


def transition(
    state: VisitState | None,
    event: Event,
    *,
    actor=None,
    reason: UnverifiedReason | None = None,
    has_photo: bool = False,
    checked_out: bool = False,
    current_reason: UnverifiedReason | None = None,
    time_unproven: bool = False,
    form_missing: bool = False,
) -> Outcome:
    """Pure transition function: (state, event, guards) -> next state and unverified reason."""
    if event in HUMAN_EVENTS and actor is None:
        raise InvalidTransition(f"{event} requires a human actor")

    match (state, event):
        case (None, Event.CHECK_IN_PASSED):
            return Outcome(S.IN_PROGRESS, None)
        case (None, Event.CHECK_IN_FAILED):
            if reason is None:
                raise InvalidTransition("a failed check-in needs a reason")
            return Outcome(S.UNVERIFIED, reason)

        case (S.IN_PROGRESS, Event.CHECK_OUT):
            if time_unproven:
                # Recorded offline and the phone could not prove when: a person reviews it (Q8).
                return Outcome(S.UNVERIFIED, UnverifiedReason.TIME_UNPROVEN)
            if form_missing:
                # The agent could not save the visit's form and said why: a person reviews it.
                return Outcome(S.UNVERIFIED, UnverifiedReason.FORM_MISSING)
            # Verified only once the arrival photo has reached the server.
            return Outcome(S.VERIFIED, None) if has_photo else Outcome(S.IN_PROGRESS, None)
        case (S.IN_PROGRESS, Event.PHOTO_ATTACHED):
            return Outcome(S.VERIFIED, None) if checked_out else Outcome(S.IN_PROGRESS, None)
        case (S.IN_PROGRESS, Event.AUTO_CLOSE):
            # BR-8. A checked-out visit still here is only waiting for its photo.
            return Outcome(
                S.UNVERIFIED,
                UnverifiedReason.NO_PHOTO if checked_out else UnverifiedReason.NO_CHECKOUT,
            )

        # A visit whose check-in check failed stays unverified; check-out and the photo
        # are still recorded as evidence for the reviewer.
        case (S.UNVERIFIED, Event.CHECK_OUT | Event.PHOTO_ATTACHED):
            return Outcome(S.UNVERIFIED, current_reason)
        case (S.UNVERIFIED, Event.AUTO_CLOSE):
            # BR-8 applies to every visit without a check-out.
            return Outcome(S.UNVERIFIED, UnverifiedReason.NO_CHECKOUT)

        case (S.UNVERIFIED, Event.RESOLVE_VERIFIED):
            return Outcome(S.VERIFIED, None)
        case (S.UNVERIFIED, Event.RESOLVE_MISSED):
            return Outcome(S.MISSED, None)

        case (S.VERIFIED, Event.PHOTO_ATTACHED):
            return Outcome(S.VERIFIED, None)

    raise InvalidTransition(f"no transition from {state} on {event}")


def apply(
    visit: Visit, event: Event, *, actor=None, reason=None, note=None, time_unproven=False, form_missing=False
) -> Visit:
    """Apply an event to a visit, persist it, and append an audit row."""
    before = visit.state or None
    outcome = transition(
        before,
        event,
        actor=actor,
        reason=reason,
        has_photo=visit.photo_id is not None,
        checked_out=visit.checked_out_at is not None,
        current_reason=visit.unverified_reason,
        time_unproven=time_unproven,
        form_missing=form_missing,
    )
    if outcome.state == S.MISSED and actor is None:  # belt and braces; see module docstring
        raise InvalidTransition("missed requires a human actor")

    visit.state = outcome.state
    visit.unverified_reason = outcome.reason
    if event == Event.AUTO_CLOSE:
        # BR-8: checked_out_at stays as it is. Never invent a departure time.
        visit.auto_closed = True
    if event in HUMAN_EVENTS:
        # BR-10: both resolutions record who, when and an optional note.
        visit.resolved_by = actor
        visit.resolved_at = clock.now()
        visit.resolution_note = note
    visit.save()

    changed = before != visit.state or event in HUMAN_EVENTS or event == Event.AUTO_CLOSE
    if changed or before is None:
        VisitEvent.objects.create(
            visit=visit,
            event=event,
            from_state=before,
            to_state=visit.state,
            reason=visit.unverified_reason,
            actor=actor,
            note=note,
        )
    return visit
