from django import template
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from fieldmonitoring.core.models import ProgrammeConfig

register = template.Library()


@register.simple_tag
def cdd_enabled():
    """Whether the CDD module is on: the sidebar shows its menu only then."""
    return ProgrammeConfig.get().cdd_enabled


@register.filter
def percent(value):
    return "–" if value is None else f"{round(value * 100)} %"


TASK_BADGES = {
    "todo": (_("To do"), "secondary"),
    "in_progress": (_("In progress"), "info"),
    "done": (_("Done"), "success"),
    "closed_without_form": (_("Closed without form"), "warning"),
    "not_applicable": (_("Not applicable"), "light"),
}
CYCLE_BADGES = {"active": "success", "suspended": "warning", "closed": "secondary"}


@register.simple_tag
def task_badge(status):
    label, css = TASK_BADGES.get(status, (status, "secondary"))
    return format_html('<span class="badge badge-{}">{}</span>', css, label)


@register.simple_tag
def cycle_badge(cycle):
    return format_html('<span class="badge badge-{}">{}</span>', CYCLE_BADGES.get(cycle.status, "secondary"),
                       cycle.get_status_display())
