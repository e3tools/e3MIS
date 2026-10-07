"""Story 3.1: exhaustive transitions, and no automated path to `missed`."""

import itertools

import pytest

from fieldmonitoring.visits.models import UnverifiedReason as R
from fieldmonitoring.visits.models import VisitState as S
from fieldmonitoring.visits.state_machine import AUTOMATED_EVENTS, Event as E, InvalidTransition, transition

ACTOR = object()
STATES = [None, S.IN_PROGRESS, S.VERIFIED, S.UNVERIFIED, S.MISSED]

# (from, event, guards) -> (to, reason); anything not listed must raise.
TABLE = {
    (None, E.CHECK_IN_PASSED, ()): (S.IN_PROGRESS, None),
    (None, E.CHECK_IN_FAILED, ()): (S.UNVERIFIED, R.LOCATION_FAILED),
    (S.IN_PROGRESS, E.CHECK_OUT, ("photo",)): (S.VERIFIED, None),
    (S.IN_PROGRESS, E.CHECK_OUT, ()): (S.IN_PROGRESS, None),
    (S.IN_PROGRESS, E.CHECK_OUT, ("unproven",)): (S.UNVERIFIED, R.TIME_UNPROVEN),
    (S.IN_PROGRESS, E.CHECK_OUT, ("photo", "unproven")): (S.UNVERIFIED, R.TIME_UNPROVEN),
    (S.IN_PROGRESS, E.PHOTO_ATTACHED, ("out",)): (S.VERIFIED, None),
    (S.IN_PROGRESS, E.PHOTO_ATTACHED, ()): (S.IN_PROGRESS, None),
    (S.IN_PROGRESS, E.AUTO_CLOSE, ()): (S.UNVERIFIED, R.NO_CHECKOUT),
    (S.IN_PROGRESS, E.AUTO_CLOSE, ("out",)): (S.UNVERIFIED, R.NO_PHOTO),
    (S.UNVERIFIED, E.CHECK_OUT, ()): (S.UNVERIFIED, R.LOCATION_FAILED),
    (S.UNVERIFIED, E.PHOTO_ATTACHED, ()): (S.UNVERIFIED, R.LOCATION_FAILED),
    (S.UNVERIFIED, E.AUTO_CLOSE, ()): (S.UNVERIFIED, R.NO_CHECKOUT),
    (S.UNVERIFIED, E.RESOLVE_VERIFIED, ()): (S.VERIFIED, None),
    (S.UNVERIFIED, E.RESOLVE_MISSED, ()): (S.MISSED, None),
    (S.VERIFIED, E.PHOTO_ATTACHED, ()): (S.VERIFIED, None),
}


def run(state, event, guards=()):
    return transition(
        state,
        event,
        actor=ACTOR if event in (E.RESOLVE_VERIFIED, E.RESOLVE_MISSED) else None,
        reason=R.LOCATION_FAILED,
        has_photo="photo" in guards,
        checked_out="out" in guards,
        current_reason=R.LOCATION_FAILED if state == S.UNVERIFIED else None,
        time_unproven="unproven" in guards,
    )


@pytest.mark.parametrize("key,expected", TABLE.items(), ids=lambda v: str(v))
def test_story_3_1_listed_transitions(key, expected):
    state, event, guards = key
    outcome = run(state, event, guards)
    assert (outcome.state, outcome.reason) == expected


@pytest.mark.parametrize("state,event", list(itertools.product(STATES, list(E))))
def test_story_3_1_unlisted_transitions_are_rejected(state, event):
    if any(k[0] == state and k[1] == event for k in TABLE):
        return
    with pytest.raises(InvalidTransition):
        run(state, event)


def test_story_3_1_unverified_reason_set_only_when_unverified():
    for (state, event, guards), (to, reason) in TABLE.items():
        assert (reason is not None) == (to == S.UNVERIFIED)


@pytest.mark.parametrize("event", [E.RESOLVE_VERIFIED, E.RESOLVE_MISSED])
def test_story_3_1_human_events_require_an_actor(event):
    with pytest.raises(InvalidTransition):
        transition(S.UNVERIFIED, event, actor=None)


def test_story_3_1_no_automated_sequence_reaches_missed():
    """Property: every sequence of up to 6 automated events, with any guards, never yields MISSED."""
    guard_sets = [(), ("photo",), ("out",), ("photo", "out")]
    frontier = {None}
    seen = set()
    for _ in range(6):
        next_frontier = set()
        for state in frontier:
            for event in AUTOMATED_EVENTS:
                for guards in guard_sets:
                    try:
                        outcome = run(state, event, guards)
                    except InvalidTransition:
                        continue
                    assert outcome.state != S.MISSED
                    next_frontier.add(outcome.state)
        seen |= next_frontier
        frontier = next_frontier
    assert S.MISSED not in seen
    assert {S.IN_PROGRESS, S.VERIFIED, S.UNVERIFIED} <= seen
