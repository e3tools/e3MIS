"""Checks and creates the agents of an import file, all or none.

Every agent goes through the field-agents page's own form (CreateFieldAgentForm), so the rules stay
in one place: role from the group, commune from the units, supervisor from the commune. Agents are
saved one by one inside a transaction, SCs first, so a facilitator in the same file gets the SC
created a few rows above and the page's team hand-over (hierarchy.sync_team) runs. The check is the
same run rolled back: what the preview shows is what the creation will do.
"""
import secrets

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.db import transaction
from django.http import QueryDict
from django.utils.translation import gettext as _

from administrativelevels.models import AdministrativeLevel, AdministrativeUnit
from authorization.agent_import.reader import problem, sort_problems
from authorization.agent_import.sheets import (
    AGENT_COLUMNS, AGENT_EMAIL_HEADER, AGENTS_SHEET, ASSIGNMENTS_SHEET, agent_header,
)
from authorization.agent_import.template import supervisor_label
from authorization.infrastructure.forms.create_field_agent_form import FIELD_AGENT_ROLES, CreateFieldAgentForm
from authorization.models import CustomUser, GroupRole, Role

# Form fields shown in the Agents sheet (the others land on the units or the whole file).
FORM_COLUMNS = {
    "first_name": "first_name", "last_name": "last_name", "email": "email", "phone_number": "phone_number",
    "role": "role", "groups": "group", "supervisor": "supervisor",
}


class ImportedAgentForm(CreateFieldAgentForm):
    """The page's form, same rules. Only the password hash is made once for the whole file: hashing
    takes about half a second, too long per agent in one request. All accounts share the password
    anyway; a user who changes it gets their own hash."""

    def __init__(self, *args, password_hash, **kwargs):
        super().__init__(*args, **kwargs)
        self.password_hash = password_hash

    def save(self, commit=True):
        self.cleaned_data["password1"] = ""
        self.instance.password = self.password_hash
        return super().save(commit=commit)


class _Rollback(Exception):
    pass


class Units:
    """Unit names to units, along their paths (names are unique only under their parent)."""

    def __init__(self):
        self.levels = list(AdministrativeLevel.objects.order_by("order"))
        self.by_parent = {}
        for pk, name, parent_id in AdministrativeUnit.objects.values_list("pk", "name", "parent_id"):
            self.by_parent[(parent_id, name.casefold())] = pk
        self.names = dict(AdministrativeUnit.objects.values_list("pk", "name"))

    def resolve(self, path):
        """``(unit id, None)`` or ``(None, (column, message))``."""
        parent = None
        for depth, name in enumerate(path):
            pk = self.by_parent.get((parent, name.casefold()))
            level = self.levels[depth].name if depth < len(self.levels) else ""
            if pk is None:
                if parent is None:
                    message = _('"%(name)s" is not a known %(level)s.') % {"name": name, "level": level}
                else:
                    message = _('"%(name)s" is not a %(level)s of %(parent)s.') % {
                        "name": name, "level": level, "parent": self.names[parent]}
                return None, (level, message)
            parent = pk
        return parent, None


def _role(value):
    """The role code for a label or code from the file; "" when empty; None when unknown."""
    if not value:
        return ""
    folded = value.casefold()
    return next((role.value for role in FIELD_AGENT_ROLES if folded in (role.value, role.label.casefold())), None)


def _supervisor_email(value):
    """The email in "Name (email)" as the list shows SCs, or the value itself."""
    if value.endswith(")") and "(" in value:
        return value[value.rindex("(") + 1:-1].strip()
    return value


def _check(agents):
    """Matches names to roles, groups and units. Returns ``(prepared, errors)``: one dict per agent
    with the form data, or with ``skip`` when a name did not match."""
    errors, prepared = [], []
    units = Units()
    groups = {name.casefold(): pk for pk, name in Group.objects.values_list("pk", "name")}
    group_roles = dict(GroupRole.objects.values_list("group_id", "role"))
    existing = {email.casefold() for email in CustomUser.objects.values_list("email", flat=True)}
    seen = {}
    sheet = str(AGENTS_SHEET)

    for agent in agents:
        row, failed = agent["row"], False

        def fail(column, message, sheet=sheet, row=row):
            nonlocal failed
            failed = True
            errors.append(problem(sheet, row, column, message))

        email = agent["email"]
        if email:
            key = email.casefold()
            if key in existing:
                fail(agent_header("email"), _("An account with this email already exists."))
            elif key in seen:
                fail(agent_header("email"), _("Also on row %(row)s of this sheet.") % {"row": seen[key]})
            seen.setdefault(key, row)

        role = _role(agent["role"])
        if role is None:
            fail(agent_header("role"), _('"%(value)s" is not a role from the list.') % {"value": agent["role"]})
        group_id = None
        if agent["group"]:
            group_id = groups.get(agent["group"].casefold())
            if group_id is None:
                fail(agent_header("group"), _('"%(value)s" is not an existing group.') % {"value": agent["group"]})

        unit_ids = []
        for unit in agent["units"]:
            pk, error = units.resolve(unit["path"])
            if error:
                fail(error[0], error[1], sheet=str(ASSIGNMENTS_SHEET), row=unit["row"])
            elif pk not in unit_ids:
                unit_ids.append(pk)

        if agent.get("invalid_units") or any(not agent[key] for key, _header, required in AGENT_COLUMNS if required):
            failed = True  # already reported by the reader
        prepared.append({
            "agent": agent,
            "skip": failed,
            # Sort key: SCs first, so facilitators in the same file find them.
            "is_sc": (role or group_roles.get(group_id)) == Role.SC,
            "data": {
                "first_name": agent["first_name"], "last_name": agent["last_name"], "email": email,
                "phone_number": agent["phone_number"], "role": role or "",
                "groups": [group_id] if group_id else [], "administrative_units": unit_ids,
                "supervisor": _supervisor_email(agent["supervisor"]),
            },
        })
    return prepared, errors


def _form_errors(agent, form):
    errors = []
    for field, messages in form.errors.items():
        for message in messages:
            if field == "administrative_units":
                rows = [unit["row"] for unit in agent["units"]]
                errors.append(problem(ASSIGNMENTS_SHEET, rows[0] if rows else None, AGENT_EMAIL_HEADER, _(
                    "%(email)s: %(message)s"
                ) % {"email": agent["email"], "message": message}))
            elif field in FORM_COLUMNS:
                errors.append(problem(AGENTS_SHEET, agent["row"], agent_header(FORM_COLUMNS[field]), message))
            else:
                errors.append(problem(AGENTS_SHEET, agent["row"], "", message))
    return errors


def run(agents, password=None, commit=False):
    """Checks (``commit=False``) or creates the agents. Returns ``(results, errors)``; nothing is
    saved unless ``commit`` and no error. ``results`` describe each agent as created."""
    prepared, errors = _check(agents)
    # The check needs a password the validators accept; it is never saved.
    raw = password or secrets.token_urlsafe(24)
    password_hash = make_password(password) if commit else make_password(None)
    results = []
    try:
        with transaction.atomic():
            for item in sorted(prepared, key=lambda item: not item["is_sc"]):
                if item["skip"]:
                    continue
                data, agent = item["data"], item["agent"]
                query = QueryDict(mutable=True)
                for key in ("first_name", "last_name", "email", "phone_number", "role"):
                    query[key] = data[key]
                query["password1"] = query["password2"] = raw
                query.setlist("groups", [str(pk) for pk in data["groups"]])
                query.setlist("administrative_units", [str(pk) for pk in data["administrative_units"]])
                if data["supervisor"]:
                    supervisor = CustomUser.objects.filter(role=Role.SC, email__iexact=data["supervisor"]).first()
                    if supervisor is None:
                        errors.append(problem(AGENTS_SHEET, agent["row"], agent_header("supervisor"), _(
                            '"%(value)s" is not an SC.'
                        ) % {"value": agent["supervisor"]}))
                        continue
                    query["supervisor"] = str(supervisor.pk)
                form = ImportedAgentForm(data=query, password_hash=password_hash)
                if not form.is_valid():
                    errors.extend(_form_errors(agent, form))
                    continue
                user = form.save()
                unit_names = dict(
                    AdministrativeUnit.objects.filter(pk__in=data["administrative_units"]).values_list("pk", "name")
                )
                results.append({
                    "row": agent["row"],
                    "name": user.get_full_name(),
                    "email": user.email,
                    "role": user.get_role_display(),
                    "role_code": user.role,
                    "group": ", ".join(user.groups.values_list("name", flat=True)),
                    "units": [unit_names[pk] for pk in data["administrative_units"]],
                    "commune": user.commune.name if user.commune_id else (user.region.name if user.region_id else ""),
                    "supervisor": supervisor_label(user.supervisor) if user.supervisor_id else "",
                })
            if errors or not commit:
                raise _Rollback
    except _Rollback:
        pass
    results.sort(key=lambda result: result["row"])
    return results, sort_problems(errors)
