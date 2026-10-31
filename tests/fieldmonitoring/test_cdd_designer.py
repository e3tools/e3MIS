"""CDD step 2: the MIS cycle designer (cdd/designer.py, CDD-12…CDD-15) and the "Cycles per community"
pages (bulk start CDD-11, status CDD-10)."""
import json
from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from administrativelevels.models import AdministrativeUnit
from cdd import designer, services
from cdd.models import Activity, Cycle, CycleEventKind, CycleStatus, CycleTemplate, Phase, Task, TaskForm, TaskKind
from tests.conftest import client_for
from trackableobjects.models import FollowUpEvent, FollowUpEventResponse, TrackableObject

from .conftest import make_user
from authorization.models import Role

START = date(2026, 1, 5)


@pytest.fixture(autouse=True)
def enabled(config):
    config.cdd_enabled = True
    config.save()
    return config


@pytest.fixture
def group(db):
    return Group.objects.create(name="Agents CDD")


@pytest.fixture
def meeting_form(group):
    form = FollowUpEvent.objects.create(name="Compte rendu", description="", jsonForm={"form": []})
    form.groups.add(group)
    return form


@pytest.fixture
def record_type(db):
    return TrackableObject.objects.create(name="Sous-projet", description="", jsonForm={"form": []})


@pytest.fixture
def template(meeting_form):
    template = CycleTemplate.objects.create(name="Cycle")
    phase = Phase.objects.create(template=template, order=1, name="Information")
    activity = Activity.objects.create(phase=phase, order=1, name="Assemblées")
    meeting = Task.objects.create(activity=activity, order=1, key="assemblee", name="Assemblée",
                                  kind=TaskKind.MEETING, planned_offset_days=10)
    TaskForm.objects.create(task=meeting, follow_up_event=meeting_form)
    Task.objects.create(activity=activity, order=2, key="cloture", name="Clôture", kind=TaskKind.MANUAL)
    return template


@pytest.fixture
def phase(template):
    return template.phases.get()


@pytest.fixture
def activity(phase):
    return phase.activities.get()


@pytest.fixture
def villages(levels, commune):
    return [AdministrativeUnit.objects.create(name=name, level=levels["village"], parent=commune)
            for name in ("Agboville", "Bécédi", "Cechi")]


@pytest.fixture
def staff(db):
    from authorization.models import CustomUser

    return client_for(CustomUser.objects.create_user(email="mis@example.test", password="x", is_staff=True))


def version(template):
    template.refresh_from_db()
    return template.version


# --- Access ---------------------------------------------------------------------------------------

def test_cdd_pages_need_the_module_switched_on(staff, enabled, template):
    assert staff.get(reverse("cdd:template_detail", args=[template.pk])).status_code == 200
    enabled.cdd_enabled = False
    enabled.save()
    assert staff.get(reverse("cdd:template_detail", args=[template.pk])).status_code == 404
    assert staff.get(reverse("cdd:cycle_list")).status_code == 404


def test_cdd_pages_are_for_mis_staff_not_field_agents(fc, template):
    fc.is_field_agent = True
    fc.save()
    assert client_for(fc).get(reverse("cdd:template_list")).status_code == 403


def test_cdd_menu_shows_only_when_the_module_is_on(staff, enabled):
    page = staff.get(reverse("authorization:app_settings"))
    assert reverse("cdd:cycle_list") in page.content.decode()
    enabled.cdd_enabled = False
    enabled.save()
    page = staff.get(reverse("authorization:app_settings"))
    assert reverse("cdd:cycle_list") not in page.content.decode()


# --- Designer -------------------------------------------------------------------------------------

def test_designer_pages_render(staff, template, activity):
    task = Task.objects.get(key="assemblee")
    for url in [
        reverse("cdd:template_list"), reverse("cdd:template_create"), reverse("cdd:template_detail", args=[template.pk]),
        reverse("cdd:template_edit", args=[template.pk]), reverse("cdd:phase_add", args=[template.pk]),
        reverse("cdd:activity_add", args=[activity.phase_id]), reverse("cdd:task_add", args=[activity.pk]),
        reverse("cdd:task_edit", args=[task.pk]), reverse("cdd:node_delete", args=["task", task.pk]),
    ]:
        assert staff.get(url).status_code == 200, url


def test_designer_creates_a_template_then_a_phase(staff):
    response = staff.post(reverse("cdd:template_create"), {"name": "Cycle COSO", "description": "", "is_active": "on"})
    template = CycleTemplate.objects.get(name="Cycle COSO")
    assert response.url == reverse("cdd:template_detail", args=[template.pk])
    staff.post(reverse("cdd:phase_add", args=[template.pk]), {"name": "Mobilisation", "planned_days": "30"})
    staff.post(reverse("cdd:phase_add", args=[template.pk]), {"name": "Diagnostic"})
    assert list(template.phases.values_list("name", "order")) == [("Mobilisation", 1), ("Diagnostic", 2)]


def task_payload(**extra):
    data = {
        "name": "Diagnostic participatif", "key": "", "kind": "form", "required": "on",
        "planned_offset_days": "60", "instructions": "",
        "forms-TOTAL_FORMS": "1", "forms-INITIAL_FORMS": "0", "forms-MIN_NUM_FORMS": "0", "forms-MAX_NUM_FORMS": "1000",
        "forms-0-form": "", "forms-0-min_count": "1", "forms-0-required": "on",
    }
    data.update(extra)
    return data


def test_cdd_12_every_change_to_the_tree_raises_the_version(staff, template, activity, record_type):
    before = version(template)
    staff.post(reverse("cdd:task_add", args=[activity.pk]), task_payload(**{"forms-0-form": f"to:{record_type.pk}"}))
    assert version(template) == before + 1
    staff.post(reverse("cdd:activity_edit", args=[activity.pk]), {"name": "Assemblées villageoises"})
    assert version(template) == before + 2
    ids = list(Task.objects.filter(activity=activity).order_by("-order").values_list("pk", flat=True))
    staff.post(reverse("cdd:tree_reorder", args=[template.pk]), json.dumps({"kind": "task", "ordered_ids": ids}),
               content_type="application/json")
    assert version(template) == before + 3


def test_designer_task_gets_its_form_and_a_key_from_its_name(staff, template, activity, record_type, meeting_form):
    staff.post(reverse("cdd:task_add", args=[activity.pk]), task_payload(**{
        "forms-0-form": f"fe:{meeting_form.pk}", "forms-0-min_count": "2",
        "depends_on": [Task.objects.get(key="assemblee").pk],
    }))
    task = Task.objects.get(name="Diagnostic participatif")
    assert task.key == "diagnostic-participatif"
    assert task.order == 3
    assert [(f.ref, f.min_count) for f in task.forms.all()] == [(f"fe:{meeting_form.pk}", 2)]
    assert list(task.depends_on.values_list("key", flat=True)) == ["assemblee"]


def test_designer_task_without_a_form_row_is_marked_by_hand(staff, activity):
    response = staff.post(reverse("cdd:task_add", args=[activity.pk]), task_payload(kind="manual"))
    assert response.status_code == 302
    assert not Task.objects.get(name="Diagnostic participatif").forms.exists()


def test_designer_edits_and_removes_a_task_form(staff, template, meeting_form, record_type):
    task = Task.objects.get(key="assemblee")
    task_form = task.forms.get()
    staff.post(reverse("cdd:task_edit", args=[task.pk]), task_payload(**{
        "name": "Assemblée", "key": "assemblee", "kind": "meeting",
        "forms-TOTAL_FORMS": "2", "forms-INITIAL_FORMS": "1",
        "forms-0-id": task_form.pk, "forms-0-task": task.pk, "forms-0-form": f"fe:{meeting_form.pk}",
        "forms-0-min_count": "1", "forms-0-required": "on", "forms-0-DELETE": "on",
        "forms-1-form": f"to:{record_type.pk}", "forms-1-min_count": "1", "forms-1-required": "on",
    }))
    assert [f.ref for f in task.forms.all()] == [f"to:{record_type.pk}"]


def test_cdd_13_new_keys_are_unique_in_the_template(template):
    assert designer.new_key(template, "Assemblée") == "assemblee-2"
    assert designer.new_key(template, "Clôture du cycle") == "cloture-du-cycle"


def test_cdd_13_duplicate_key_is_refused(staff, activity):
    response = staff.post(reverse("cdd:task_add", args=[activity.pk]), task_payload(key="cloture"))
    assert response.status_code == 200
    assert "key" in response.context["form"].errors


def test_cdd_13_key_is_fixed_once_a_cycle_follows_the_template(staff, template, village):
    task = Task.objects.get(key="cloture")
    staff.post(reverse("cdd:task_edit", args=[task.pk]), task_payload(name="Clôture", key="fin", kind="manual"))
    task.refresh_from_db()
    assert task.key == "fin"  # no cycle yet: editable
    services.start_cycle(template, village, started_on=START)
    staff.post(reverse("cdd:task_edit", args=[task.pk]), task_payload(name="Clôture", key="autre", kind="manual"))
    task.refresh_from_db()
    assert (task.key, task.name) == ("fin", "Clôture")


def test_cdd_14_starts_after_may_not_loop_back(staff, template):
    first, last = Task.objects.get(key="assemblee"), Task.objects.get(key="cloture")
    last.depends_on.add(first)
    response = staff.post(reverse("cdd:task_edit", args=[first.pk]), task_payload(
        name="Assemblée", key="assemblee", kind="meeting", depends_on=[last.pk]))
    assert response.status_code == 200
    assert not first.depends_on.exists()
    assert designer.loops_back(first, [last]) and not designer.loops_back(last, [first])


def test_designer_reorders_phases_activities_and_tasks(staff, template, phase):
    second = Phase.objects.create(template=template, order=2, name="Diagnostic")
    staff.post(reverse("cdd:tree_reorder", args=[template.pk]),
               json.dumps({"kind": "phase", "ordered_ids": [second.pk, phase.pk]}), content_type="application/json")
    assert list(template.phases.order_by("order").values_list("name", flat=True)) == ["Diagnostic", "Information"]


def test_designer_reorder_ignores_nodes_of_other_templates(staff, template):
    other = CycleTemplate.objects.create(name="Autre")
    foreign = Phase.objects.create(template=other, order=5, name="Ailleurs")
    response = staff.post(reverse("cdd:tree_reorder", args=[template.pk]),
                          json.dumps({"kind": "phase", "ordered_ids": [foreign.pk]}), content_type="application/json")
    assert response.status_code == 200
    foreign.refresh_from_db()
    assert foreign.order == 5
    bad = staff.post(reverse("cdd:tree_reorder", args=[template.pk]), "{}", content_type="application/json")
    assert bad.status_code == 400


def test_designer_delete_says_how_many_answers_point_at_the_tasks(staff, template, phase, village, meeting_form, fc):
    cycle = services.start_cycle(template, village, started_on=START)
    FollowUpEventResponse.objects.create(follow_up_event=meeting_form, created_by=fc, jsonForm={},
                                         cdd_cycle=cycle, cdd_task_key="assemblee")
    page = staff.get(reverse("cdd:node_delete", args=["phase", phase.pk]))
    assert page.context["answer_count"] == 1
    assert page.context["task_names"] == ["Assemblée", "Clôture"]
    before = version(template)
    staff.post(reverse("cdd:node_delete", args=["phase", phase.pk]))
    assert not template.phases.exists()
    assert version(template) == before + 1
    assert FollowUpEventResponse.objects.filter(cdd_task_key="assemblee").exists()  # answers kept


def test_cdd_15_designer_warns_when_facilitators_cannot_fill_a_form(template, village, fc, group, meeting_form):
    task_form = TaskForm.objects.get(task__key="assemblee")
    assert designer.form_warnings(template) == {}  # no active cycle yet, the form has a group
    services.start_cycle(template, village, facilitators=[fc], started_on=START)
    warnings = designer.form_warnings(template)[task_form.pk]
    assert len(warnings) == 1 and "Mariam" in warnings[0]
    fc.groups.add(group)
    assert designer.form_warnings(template) == {}


def test_cdd_15_designer_warns_on_inactive_forms_and_forms_without_group(template, meeting_form, group):
    meeting_form.groups.remove(group)
    meeting_form.is_active = False
    meeting_form.save()
    task_form = TaskForm.objects.get(task__key="assemblee")
    assert len(designer.form_warnings(template)[task_form.pk]) == 2


# --- Cycles per community -------------------------------------------------------------------------

def test_cycle_pages_render(staff, template, village, fc):
    cycle = services.start_cycle(template, village, facilitators=[fc], started_on=START)
    for url in [reverse("cdd:cycle_list"), reverse("cdd:cycle_start"), reverse("cdd:cycle_detail", args=[cycle.pk]),
                f"{reverse('cdd:cycle_communities')}?commune={village.parent_id}"]:
        assert staff.get(url).status_code == 200, url


def test_cdd_11_start_lists_the_communities_of_a_commune_and_marks_active_ones(staff, template, commune, villages):
    services.start_cycle(template, villages[0], started_on=START)
    page = staff.get(f"{reverse('cdd:cycle_communities')}?commune={commune.pk}")
    rows = [(unit.name, active is not None) for unit, active in page.context["rows"]]
    assert rows == [("Agboville", True), ("Bécédi", False), ("Cechi", False)]


def start_payload(template, commune, communities, **extra):
    data = {
        "template": template.pk, "commune": commune.pk, "communities": [u.pk for u in communities],
        "started_on": "2026-01-05", "planned_end": "", "with_attached": "on",
    }
    data.update(extra)
    return data


def test_cdd_11_bulk_start_gives_each_community_its_attached_facilitators(staff, template, commune, villages, fc,
                                                                          other_commune):
    village_ft = make_user("salif", Role.FT, commune=commune)
    village_ft.administrative_units.add(villages[1])
    elsewhere = make_user("yacouba", Role.FC, commune=other_commune)
    extra = make_user("aya", Role.FC, commune=other_commune)
    response = staff.post(reverse("cdd:cycle_start"),
                          start_payload(template, commune, villages[1:], facilitators=[extra.pk]))
    assert response.status_code == 302
    cycles = {c.community.name: set(c.facilitators.values_list("email", flat=True)) for c in Cycle.objects.all()}
    # fc is attached by their commune (no unit), salif by the village, aya added by hand; yacouba is elsewhere.
    assert cycles == {
        "Bécédi": {fc.email, village_ft.email, extra.email},
        "Cechi": {fc.email, extra.email},
    }
    assert elsewhere.email not in set().union(*cycles.values())
    assert all(c.started_on == START and c.created_by.email == "mis@example.test" for c in Cycle.objects.all())


def test_cdd_11_bulk_start_without_attached_facilitators(staff, template, commune, villages, fc):
    staff.post(reverse("cdd:cycle_start"), start_payload(template, commune, villages[:1], with_attached=""))
    assert not Cycle.objects.get().facilitators.exists()


def test_cdd_9_bulk_start_skips_communities_that_have_an_active_cycle(template, villages):
    services.start_cycle(template, villages[0], started_on=START)
    started, skipped = services.start_cycles(template, villages, started_on=START, with_attached=False)
    assert [c.community.name for c in started] == ["Bécédi", "Cechi"]
    assert [u.name for u, _reason in skipped] == ["Agboville"]


def test_cycle_start_refuses_a_community_with_an_active_cycle(staff, template, commune, villages):
    services.start_cycle(template, villages[0], started_on=START)
    response = staff.post(reverse("cdd:cycle_start"), start_payload(template, commune, villages[:1]))
    assert response.status_code == 200  # not offered, so the choice is invalid
    assert Cycle.objects.count() == 1


def test_cycle_start_planned_end_not_before_start(staff, template, commune, villages):
    response = staff.post(reverse("cdd:cycle_start"),
                          start_payload(template, commune, villages[:1], planned_end="2025-12-31"))
    assert response.status_code == 200
    assert not Cycle.objects.exists()


def test_cycle_list_filters_by_commune_and_status(staff, template, villages, other_commune, levels):
    elsewhere = AdministrativeUnit.objects.create(name="Gbazé", level=levels["village"], parent=other_commune)
    services.start_cycle(template, villages[0], started_on=START)
    closed = services.start_cycle(template, elsewhere, started_on=START)
    services.set_status(closed, CycleStatus.CLOSED, note="Fin du financement")
    page = staff.get(reverse("cdd:cycle_list"), {"commune": villages[0].parent_id})
    assert [r["cycle"].community.name for r in page.context["rows"]] == ["Agboville"]
    page = staff.get(reverse("cdd:cycle_list"), {"status": "closed"})
    assert [r["cycle"].community.name for r in page.context["rows"]] == ["Gbazé"]


def test_cdd_10_cycle_status_needs_a_reason_from_the_page(staff, template, village):
    cycle = services.start_cycle(template, village, started_on=START)
    url = reverse("cdd:cycle_status", args=[cycle.pk])
    staff.post(url, {"status": "closed", "note": ""})
    cycle.refresh_from_db()
    assert cycle.status == CycleStatus.ACTIVE
    staff.post(url, {"status": "closed", "note": "Communauté déplacée"})
    cycle.refresh_from_db()
    assert cycle.status == CycleStatus.CLOSED
    event = cycle.events.first()
    assert (event.kind, event.note, event.by.email) == (CycleEventKind.CLOSED, "Communauté déplacée", "mis@example.test")


def test_cycle_facilitators_are_saved_and_the_version_goes_up(staff, template, village, fc, ft):
    cycle = services.start_cycle(template, village, facilitators=[fc], started_on=START)
    staff.post(reverse("cdd:cycle_facilitators", args=[cycle.pk]), {"facilitators": [ft.pk]})
    cycle.refresh_from_db()
    assert list(cycle.facilitators.all()) == [ft]
    assert cycle.version == 2


def test_cycle_detail_shows_tasks_forms_and_history(staff, template, village, fc, meeting_form):
    cycle = services.start_cycle(template, village, facilitators=[fc], started_on=START)
    FollowUpEventResponse.objects.create(follow_up_event=meeting_form, created_by=fc, jsonForm={},
                                         cdd_cycle=cycle, cdd_task_key="assemblee")
    services.decide_task(cycle, "cloture", "not_applicable", by=fc, note="Pas prévu")
    page = staff.get(reverse("cdd:cycle_detail", args=[cycle.pk]))
    html = page.content.decode()
    assert page.context["state"].task("assemblee").status == "done"
    assert "Pas prévu" in html
    assert reverse("trackableobjects:follow_up_event_response_detail", args=[
        FollowUpEventResponse.objects.get().pk]) in html
