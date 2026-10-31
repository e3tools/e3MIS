"""CDD cycle: progress rules CDD-1…CDD-8 (cdd/progress.py) and services CDD-9, CDD-10 (cdd/services.py)."""
from datetime import date, datetime, timedelta, timezone

import pytest
import time_machine
from django.core.exceptions import ValidationError
from django.core.management import call_command

from cdd import progress, services
from cdd.models import (
    Activity, Cycle, CycleEvent, CycleEventKind, CycleStatus, CycleTemplate, Phase, Task, TaskForm, TaskKind,
)
from cdd.progress import (
    CLOSED_WITHOUT_FORM, DONE, IN_PROGRESS, NOT_APPLICABLE, TODO, FormNeed, PhaseSpec, Snapshot, TaskSpec,
)
from trackableobjects.models import FollowUpEvent, FollowUpEventResponse, TrackableObject, TrackableObjectInstance

START = date(2026, 1, 5)
MINUTES, LIST = FormNeed("fe:1"), FormNeed("fe:2", min_count=2)


def snap(tasks, phases=None, status=CycleStatus.ACTIVE, evidence=None, decisions=None, last_activity=None):
    return Snapshot(
        status=status, started_on=START, phases=phases or [PhaseSpec(1, "P1")], tasks=tasks,
        evidence=evidence or {}, decisions=decisions or {}, last_activity=last_activity,
    )


def evaluate(snapshot, today=START, inactive_days=21):
    return progress.evaluate(snapshot, today, inactive_days)


# --- Progress rules (plain data) ------------------------------------------------------------------

def test_cdd_1_task_with_forms_is_done_when_each_required_form_has_its_answers():
    spec = TaskSpec("t", "T", 1, forms=(MINUTES, LIST))
    assert progress.task_status(spec, {}) == TODO
    assert progress.task_status(spec, {"fe:1": 1}) == IN_PROGRESS
    assert progress.task_status(spec, {"fe:1": 1, "fe:2": 1}) == IN_PROGRESS  # min_count 2 not reached
    assert progress.task_status(spec, {"fe:1": 1, "fe:2": 2}) == DONE
    assert progress.task_status(spec, {"fe:1": 3, "fe:2": 5}) == DONE


def test_cdd_1_optional_forms_are_not_needed_to_be_done():
    spec = TaskSpec("t", "T", 1, forms=(MINUTES, FormNeed("fe:9", required=False)))
    assert progress.task_status(spec, {"fe:1": 1}) == DONE


def test_cdd_1_answers_of_other_forms_are_not_evidence():
    spec = TaskSpec("t", "T", 1, forms=(MINUTES,))
    assert progress.task_status(spec, {"fe:7": 4}) == TODO


def test_cdd_2_task_without_required_forms_is_done_only_when_marked():
    manual = TaskSpec("t", "T", 1)
    assert progress.task_status(manual, {}) == TODO
    assert progress.task_status(manual, {}, DONE) == DONE
    optional_form = TaskSpec("t", "T", 1, forms=(FormNeed("fe:9", required=False),))
    assert progress.task_status(optional_form, {"fe:9": 1}) == IN_PROGRESS
    assert progress.task_status(optional_form, {"fe:9": 1}, DONE) == DONE


def test_cdd_3_decisions_win_over_evidence_and_count_apart():
    tasks = [TaskSpec("a", "A", 1, forms=(MINUTES,)), TaskSpec("b", "B", 1, forms=(MINUTES,)),
             TaskSpec("c", "C", 1, forms=(MINUTES,))]
    state = evaluate(snap(tasks, evidence={"a": {"fe:1": 1}, "b": {"fe:1": 1}},
                          decisions={"a": CLOSED_WITHOUT_FORM, "b": NOT_APPLICABLE}))
    assert [t.status for t in state.tasks] == [CLOSED_WITHOUT_FORM, NOT_APPLICABLE, TODO]
    # Not applicable leaves the counts; closed without form counts as completed and apart.
    assert (state.completed, state.total) == (1, 2)
    assert state.closed_without_form_count == 1


def test_cdd_4_progress_counts_required_tasks_that_apply():
    phases = [PhaseSpec(1, "P1"), PhaseSpec(2, "P2")]
    tasks = [
        TaskSpec("a", "A", 1, forms=(MINUTES,)),
        TaskSpec("b", "B", 1),
        TaskSpec("opt", "Optional", 1, required=False),
        TaskSpec("c", "C", 2),
    ]
    state = evaluate(snap(tasks, phases, evidence={"a": {"fe:1": 1}}, decisions={"opt": DONE}))
    assert [(p.completed, p.total) for p in state.phases] == [(1, 2), (0, 1)]
    assert state.phases[0].progress == 0.5
    assert (state.completed, state.total) == (1, 3)
    empty = evaluate(snap([TaskSpec("opt", "Optional", 1, required=False)]))
    assert empty.progress is None and empty.phases[0].progress is None


def test_cdd_5_current_phase_is_the_first_with_an_open_required_task():
    phases = [PhaseSpec(1, "P1"), PhaseSpec(2, "P2"), PhaseSpec(3, "P3")]
    tasks = [TaskSpec("a", "A", 1), TaskSpec("b", "B", 2), TaskSpec("opt", "O", 2, required=False),
             TaskSpec("c", "C", 3)]
    assert evaluate(snap(tasks, phases)).current_phase_id == 1
    # Phase 2: its only required task does not apply → phase 3 is current, whatever the optional task.
    state = evaluate(snap(tasks, phases, decisions={"a": DONE, "b": NOT_APPLICABLE}))
    assert state.current_phase_id == 3
    done = evaluate(snap(tasks, phases, decisions={"a": DONE, "b": DONE, "c": CLOSED_WITHOUT_FORM}))
    assert done.current_phase_id is None and done.progress == 1


def test_cdd_6_overdue_from_the_day_after_the_due_date():
    tasks = [TaskSpec("a", "A", 1, offset_days=10), TaskSpec("none", "No due date", 1)]
    due = START + timedelta(days=10)
    on_due_date = evaluate(snap(tasks), today=due)
    assert on_due_date.task("a").due_on == due and on_due_date.task("a").overdue_days == 0
    after = evaluate(snap(tasks), today=due + timedelta(days=1))
    assert after.task("a").overdue_days == 1 and after.task("none").overdue_days == 0
    assert after.overdue_count == 1


def test_cdd_6_no_overdue_for_settled_tasks_or_cycles_not_active():
    tasks = [TaskSpec("a", "A", 1, offset_days=0)]
    late = START + timedelta(days=30)
    assert evaluate(snap(tasks, decisions={"a": DONE}), today=late).task("a").overdue_days == 0
    assert evaluate(snap(tasks, decisions={"a": NOT_APPLICABLE}), today=late).task("a").overdue_days == 0
    for status in (CycleStatus.SUSPENDED, CycleStatus.CLOSED):
        assert evaluate(snap(tasks, status=status), today=late).overdue_count == 0


def test_cdd_7_warning_when_started_before_a_task_it_depends_on():
    tasks = [TaskSpec("a", "A", 1), TaskSpec("b", "B", 1, depends_on=("a",), forms=(MINUTES,))]
    started = evaluate(snap(tasks, evidence={"b": {"fe:1": 1}}))
    # A warning, not a block: the task is done all the same.
    assert started.task("b").status == DONE and started.task("b").waiting_on == ["a"]
    assert evaluate(snap(tasks)).task("b").waiting_on == []  # not started yet
    for decision in (DONE, NOT_APPLICABLE, CLOSED_WITHOUT_FORM):
        settled = evaluate(snap(tasks, evidence={"b": {"fe:1": 1}}, decisions={"a": decision}))
        assert settled.task("b").waiting_on == []


def test_cdd_8_inactive_after_the_configured_number_of_days():
    tasks = [TaskSpec("a", "A", 1)]
    last = START + timedelta(days=3)
    assert not evaluate(snap(tasks, last_activity=last), today=last + timedelta(days=20)).inactive
    state = evaluate(snap(tasks, last_activity=last), today=last + timedelta(days=21))
    assert state.inactive and state.idle_days == 21
    # No activity at all: counted from the start.
    assert evaluate(snap(tasks), today=START + timedelta(days=21)).inactive
    closed = evaluate(snap(tasks, status=CycleStatus.CLOSED), today=START + timedelta(days=90))
    assert not closed.inactive


# --- Database ------------------------------------------------------------------------------------

@pytest.fixture
def meeting_form(db):
    return FollowUpEvent.objects.create(name="Compte rendu", description="", jsonForm={"form": []})


@pytest.fixture
def record_type(db):
    return TrackableObject.objects.create(name="Sous-projet", description="", jsonForm={"form": []})


@pytest.fixture
def template(meeting_form, record_type):
    template = CycleTemplate.objects.create(name="Cycle")
    phase = Phase.objects.create(template=template, order=1, name="Information")
    activity = Activity.objects.create(phase=phase, order=1, name="Assemblées")
    meeting = Task.objects.create(activity=activity, order=1, key="assemblee", name="Assemblée",
                                  kind=TaskKind.MEETING, planned_offset_days=10)
    TaskForm.objects.create(task=meeting, follow_up_event=meeting_form)
    record = Task.objects.create(activity=activity, order=2, key="fiche", name="Fiche")
    TaskForm.objects.create(task=record, trackable_object=record_type)
    record.depends_on.add(meeting)
    Task.objects.create(activity=activity, order=3, key="cloture", name="Clôture", kind=TaskKind.MANUAL)
    return template


@pytest.fixture
def cycle(template, village, fc):
    return services.start_cycle(template, village, by=fc, facilitators=[fc], started_on=START)


def test_cdd_state_counts_answers_tagged_with_the_cycle_and_task(cycle, meeting_form, record_type, fc, config):
    FollowUpEventResponse.objects.create(follow_up_event=meeting_form, created_by=fc, jsonForm={},
                                         cdd_cycle=cycle, cdd_task_key="assemblee")
    FollowUpEventResponse.objects.create(follow_up_event=meeting_form, created_by=fc, jsonForm={})  # untagged
    FollowUpEventResponse.objects.create(follow_up_event=meeting_form, created_by=fc, jsonForm={},
                                         cdd_cycle=cycle, cdd_task_key="fiche")  # not the task's form
    TrackableObjectInstance.objects.create(trackable_object=record_type, created_by=fc, jsonForm={},
                                           cdd_cycle=cycle, cdd_task_key="fiche")
    state = progress.state(cycle, today=START, config=config)
    assert state.task("assemblee").status == DONE
    assert state.task("fiche").status == DONE
    assert state.task("cloture").status == TODO
    assert (state.completed, state.total) == (2, 3)


def test_cdd_state_last_activity_is_the_latest_answer_or_decision(template, village, meeting_form, fc, config):
    with time_machine.travel(datetime(2026, 1, 5, 9, tzinfo=timezone.utc), tick=False):
        cycle = services.start_cycle(template, village, by=fc, facilitators=[fc])
    with time_machine.travel(datetime(2026, 2, 1, 9, tzinfo=timezone.utc), tick=False):
        FollowUpEventResponse.objects.create(follow_up_event=meeting_form, created_by=fc, jsonForm={},
                                             cdd_cycle=cycle, cdd_task_key="assemblee")
    with time_machine.travel(datetime(2026, 2, 10, 9, tzinfo=timezone.utc), tick=False):
        services.decide_task(cycle, "cloture", "done", by=fc)
    state = progress.state(cycle, today=date(2026, 3, 3), config=config)
    assert state.last_activity == date(2026, 2, 10) and state.idle_days == 21 and state.inactive


def test_cdd_1_a_task_with_forms_cannot_be_marked_done(cycle, fc):
    with pytest.raises(ValidationError):
        services.decide_task(cycle, "assemblee", "done", by=fc)
    services.decide_task(cycle, "cloture", "done", by=fc)  # no forms: fine


def test_cdd_3_closing_without_form_needs_a_reason(cycle, fc):
    for status in ("closed_without_form", "not_applicable"):
        with pytest.raises(ValidationError):
            services.decide_task(cycle, "assemblee", status, by=fc, note="  ")
    decision = services.decide_task(cycle, "assemblee", "closed_without_form", by=fc, note="PV perdu")
    assert decision.decided_at is not None and decision.version == 1
    services.decide_task(cycle, "assemblee", "", by=fc)  # withdrawn
    decision.refresh_from_db()
    assert decision.manual_status == "" and decision.version == 2
    kinds = list(cycle.events.values_list("kind", flat=True))
    assert kinds[:2] == [CycleEventKind.TASK_RESET, CycleEventKind.TASK_CLOSED_WITHOUT_FORM]


def test_cdd_decision_on_an_unknown_task_is_refused(cycle, fc):
    with pytest.raises(ValidationError):
        services.decide_task(cycle, "nope", "done", by=fc)


def test_cdd_9_one_active_cycle_per_community_numbered_per_community(cycle, template, village, commune, fc):
    assert cycle.number == 1 and cycle.template_version == template.version
    assert CycleEvent.objects.filter(cycle=cycle, kind=CycleEventKind.STARTED).exists()
    with pytest.raises(ValidationError):
        services.start_cycle(template, village, by=fc)
    services.set_status(cycle, CycleStatus.CLOSED, by=fc, note="Cycle terminé")
    second = services.start_cycle(template, village, by=fc)
    assert second.number == 2
    with pytest.raises(ValidationError):  # a commune is not a community
        services.start_cycle(template, commune, by=fc)


def test_cdd_9_community_level_from_the_configuration(template, village, commune, levels, config, fc):
    config.cdd_community_level = levels["commune"]
    config.save()
    services.start_cycle(template, commune, by=fc)
    with pytest.raises(ValidationError):
        services.start_cycle(template, village, by=fc)


def test_cdd_10_status_changes_need_a_reason(cycle, template, village, fc):
    with pytest.raises(ValidationError):
        services.set_status(cycle, CycleStatus.SUSPENDED, by=fc)
    services.set_status(cycle, CycleStatus.SUSPENDED, by=fc, note="Saison des pluies")
    assert cycle.status == CycleStatus.SUSPENDED and cycle.version == 2
    other = services.start_cycle(template, village, by=fc)
    with pytest.raises(ValidationError):  # reopening would make two active cycles
        services.set_status(cycle, CycleStatus.ACTIVE, by=fc, note="Reprise")
    services.set_status(other, CycleStatus.CLOSED, by=fc, note="Ouvert par erreur")
    services.set_status(cycle, CycleStatus.ACTIVE, by=fc, note="Reprise")
    assert Cycle.objects.filter(community=village, status=CycleStatus.ACTIVE).get() == cycle


def test_cdd_task_keys_are_unique_within_a_template(template):
    task = Task(activity=Activity.objects.first(), key="assemblee", name="Doublon")
    with pytest.raises(ValidationError):
        task.full_clean()


def test_seed_cdd_cycle_is_idempotent(db, config):
    call_command("seed_cdd_cycle", "--enable", stdout=_Null())
    template = CycleTemplate.objects.get(name="Cycle CDD (exemple)")
    assert template.phases.count() == 5
    keys = set(template.tasks().values_list("key", flat=True))
    assert {"diagnostic", "identification-sous-projet", "cloture"} <= keys
    fiche = Task.objects.get(key="identification-sous-projet")
    assert fiche.forms.get().trackable_object.name == "Sous-projet"
    assert set(Task.objects.get(key="validation-plan").depends_on.values_list("key", flat=True)) == {
        "comite", "priorisation"
    }
    config.refresh_from_db()
    assert config.cdd_enabled
    version, count = template.version, Task.objects.count()
    call_command("seed_cdd_cycle", stdout=_Null())
    template.refresh_from_db()
    assert template.version == version and Task.objects.count() == count
    Task.objects.filter(key="cloture").update(name="Renamed")
    call_command("seed_cdd_cycle", stdout=_Null())
    template.refresh_from_db()
    assert template.version == version + 1


class _Null:
    def write(self, *args, **kwargs):
        pass

    def flush(self):
        pass


def test_seed_cdd_cycle_template_evaluates(db, config):
    call_command("seed_cdd_cycle", stdout=_Null())
    phases, tasks = progress.template_specs(CycleTemplate.objects.get())
    state = progress.evaluate(Snapshot(CycleStatus.ACTIVE, START, phases, tasks), START, 21)
    assert state.current_phase_id == phases[0].id
    assert state.total == sum(1 for t in tasks if t.required)


def test_seed_cdd_cycle_forms_build_in_the_mis(db, config):
    from cdd.management.commands.seed_cdd_cycle import FORMS
    from utils.json_form_parser import parse_custom_jsonschema

    call_command("seed_cdd_cycle", stdout=_Null())
    for name, _description, _schema in FORMS:
        event = FollowUpEvent.objects.get(name=name)
        fields = parse_custom_jsonschema(event.jsonForm, administrative_level_ids=None)().fields
        assert "date" in fields, name
