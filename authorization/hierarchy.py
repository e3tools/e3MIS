"""Reporting lines worked out from role and administrative unit (Brice, 29 Oct 2026).

A user is created with a role and one administrative unit; the rest follows:
- FT, FC and SC: the unit is their commune (or a unit inside it), so ``commune`` is derived.
- Regional specialist: the unit is their region (département in Benin), so ``region`` is derived.
- An FT/FC reports to the SC of their commune. A commune without an SC leaves them without a
  supervisor (their reviews go to the RdP, BR-10) until an SC is created there, who then takes
  them over. A commune with several SCs is the only case where someone picks the supervisor.
"""
from authorization.models import FACILITATOR_ROLES, CustomUser, Role
from fieldmonitoring.core.geography import commune_containing, region_containing


def commune_supervisors(commune, exclude=None):
    scs = CustomUser.objects.filter(role=Role.SC, commune=commune, is_active=True)
    if exclude is not None and exclude.pk:
        scs = scs.exclude(pk=exclude.pk)
    return scs


def scope_for(role, unit):
    """``(commune, region)`` for a user with ``role`` attached to ``unit``. A side is None when the
    unit does not reach that level (e.g. a département for an FT)."""
    if role in (Role.FT, Role.FC, Role.SC):
        return commune_containing(unit), None
    if role == Role.REGIONAL_SPECIALIST:
        return None, region_containing(unit)
    return None, None


def supervisor_for(user, commune):
    """``(supervisor, candidates)``: the SC an FT/FC reports to, and the SCs to choose from when the
    commune has several (then the supervisor is the current one if still valid, else None)."""
    candidates = list(commune_supervisors(commune, exclude=user)) if commune else []
    if len(candidates) == 1:
        return candidates[0], candidates
    current = next((sc for sc in candidates if sc.pk == user.supervisor_id), None)
    return current, candidates


def sync_team(user):
    """After ``user`` is saved: an SC takes over the facilitators of their commune who have no
    supervisor (when they are its only SC); facilitators left behind by an SC who moved or changed
    role go to their commune's SC, or to nobody."""
    stray = CustomUser.objects.filter(supervisor=user, role__in=FACILITATOR_ROLES)
    if user.role == Role.SC and user.is_active:
        stray = stray.exclude(commune_id=user.commune_id)
    for facilitator in stray.select_related("commune"):
        others = list(commune_supervisors(facilitator.commune_id, exclude=user)) if facilitator.commune_id else []
        CustomUser.objects.filter(pk=facilitator.pk).update(supervisor=others[0] if len(others) == 1 else None)
    if user.role == Role.SC and user.is_active and user.commune_id:
        if commune_supervisors(user.commune_id).count() == 1:
            CustomUser.objects.filter(
                role__in=FACILITATOR_ROLES, commune_id=user.commune_id, supervisor__isnull=True
            ).update(supervisor=user)
