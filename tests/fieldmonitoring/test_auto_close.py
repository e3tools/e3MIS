"""BR-8 / Story 3.2: nightly auto-close, in programme time, across daylight saving."""

import pytest
import time_machine

from fieldmonitoring.core.jobs import auto_close_if_due
from fieldmonitoring.visits.models import Visit
from tests.fieldmonitoring.conftest import utc

pytestmark = pytest.mark.django_db


@pytest.fixture
def paris(config):
    # A zone with daylight saving, to prove the job follows programme wall-clock time.
    config.timezone = "Europe/Paris"
    config.save()
    return config


def open_visit(check_in, user, worksite, at):
    with time_machine.travel(at, tick=False):
        return check_in(user, worksite).json()["id"]


def test_br8_open_visit_becomes_unverified_no_checkout(ft, worksite, check_in):
    visit_id = open_visit(check_in, ft, worksite, utc(2026, 9, 28, 9, 0))
    assert auto_close_if_due(utc(2026, 9, 28, 20, 0)) == 1
    visit = Visit.objects.get(pk=visit_id)
    assert (visit.state, visit.unverified_reason, visit.auto_closed) == ("unverified", "no_checkout", True)
    assert visit.checked_out_at is None and visit.time_on_site_s is None  # never invented
    assert visit.awaiting_review


def test_br8_not_before_20_00_programme_time(ft, worksite, check_in):
    open_visit(check_in, ft, worksite, utc(2026, 9, 28, 9, 0))
    assert auto_close_if_due(utc(2026, 9, 28, 19, 59)) is None


def test_br8_is_idempotent(ft, worksite, check_in):
    open_visit(check_in, ft, worksite, utc(2026, 9, 28, 9, 0))
    assert auto_close_if_due(utc(2026, 9, 28, 20, 0)) == 1
    assert auto_close_if_due(utc(2026, 9, 28, 20, 5)) is None


def test_story_3_2_check_in_19_55_check_out_20_30_is_not_auto_closed(ft, worksite, check_in, client_for):
    visit_id = open_visit(check_in, ft, worksite, utc(2026, 9, 28, 19, 55))
    auto_close_if_due(utc(2026, 9, 28, 20, 0))
    with time_machine.travel(utc(2026, 9, 28, 20, 30), tick=False):
        body = client_for(ft).post(f"/api/v1/visits/{visit_id}/check-out/",
                                   {"idempotency_key": "late"}, format="json").json()
    assert body["state"] == "verified" and not body["auto_closed"]


def test_br8_never_produces_missed(ft, worksite, check_in):
    open_visit(check_in, ft, worksite, utc(2026, 9, 28, 9, 0))
    auto_close_if_due(utc(2026, 9, 28, 20, 0))
    assert not Visit.objects.filter(state="missed").exists()


@pytest.mark.parametrize(
    "label,local_2000_utc,just_before",
    [
        # Paris is UTC+2 in summer, so 20:00 local is 18:00 UTC …
        ("summer", utc(2026, 10, 24, 18, 0), utc(2026, 10, 24, 17, 59)),
        # … and UTC+1 after the clocks go back on 25 Oct 2026, so 20:00 local is 19:00 UTC.
        ("winter", utc(2026, 10, 26, 19, 0), utc(2026, 10, 26, 18, 59)),
    ],
)
def test_br8_runs_at_20_00_local_across_dst(paris, ft, worksite, check_in, label, local_2000_utc, just_before):
    open_visit(check_in, ft, worksite, local_2000_utc.replace(hour=8))
    assert auto_close_if_due(just_before) is None
    assert auto_close_if_due(local_2000_utc) == 1


def test_br8_dst_change_day_itself(paris, ft, worksite, check_in):
    # 25 Oct 2026: the day is 25 hours long. 20:00 local is 19:00 UTC.
    open_visit(check_in, ft, worksite, utc(2026, 10, 25, 8, 0))
    assert auto_close_if_due(utc(2026, 10, 25, 18, 30)) is None
    assert auto_close_if_due(utc(2026, 10, 25, 19, 0)) == 1


def test_jobs_endpoint_requires_the_cron_secret(client, settings):
    settings.CRON_SECRET = "s3cret"
    assert client.get("/api/v1/jobs/run/").status_code == 401
    assert client.get("/api/v1/jobs/run/", HTTP_AUTHORIZATION="Bearer wrong").status_code == 401
    assert client.get("/api/v1/jobs/run/", HTTP_AUTHORIZATION="Bearer s3cret").status_code == 200


def test_jobs_endpoint_is_closed_without_a_configured_secret(client, settings):
    settings.CRON_SECRET = None
    assert client.get("/api/v1/jobs/run/", HTTP_AUTHORIZATION="Bearer None").status_code == 401
