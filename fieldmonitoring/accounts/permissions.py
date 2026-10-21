from rest_framework.permissions import BasePermission

from authorization.models import SPECIALIST_ROLES, VISITING_ROLES, Role


def has_role(*roles):
    class HasRole(BasePermission):
        def has_permission(self, request, view):
            return request.user.is_authenticated and request.user.role in roles

    HasRole.__name__ = f"HasRole_{'_'.join(roles)}"
    return HasRole


RecordsVisits = has_role(*VISITING_ROLES)
IsSupervisorOrAbove = has_role(Role.SC, Role.RDP, Role.ADMIN)
IsRdpOrAdmin = has_role(Role.RDP, Role.ADMIN)
IsAdmin = has_role(Role.ADMIN)


def can_view_user(viewer, user) -> bool:
    if viewer.pk == user.pk or viewer.role in (Role.RDP, Role.ADMIN):
        return True
    return viewer.role == Role.SC and user.supervisor_id == viewer.pk


def can_view_visit(viewer, visit) -> bool:
    """Photos and visit detail: the owner, their SC, specialists and the RdP (architecture §security)."""
    return can_view_user(viewer, visit.user) or viewer.role in SPECIALIST_ROLES


def can_resolve(viewer, visit) -> bool:
    """BR-10: the owner's SC; the RdP for anyone without a supervisor (SCs, specialists)."""
    if viewer.pk == visit.user_id:
        return False
    if viewer.role == Role.ADMIN:
        return True
    if viewer.role == Role.RDP:
        return visit.user.supervisor_id is None
    return viewer.role == Role.SC and visit.user.supervisor_id == viewer.pk


def visible_visits(viewer):
    """Visits the viewer may open: consistent with `can_view_visit`."""
    from django.db.models import Q

    from fieldmonitoring.visits.models import Visit

    visits = Visit.objects.all()
    if viewer.role in (Role.RDP, Role.ADMIN) or viewer.role in SPECIALIST_ROLES:
        return visits
    if viewer.role == Role.SC:
        return visits.filter(Q(user=viewer) | Q(user__supervisor=viewer))
    return visits.filter(user=viewer)


def visible_worksites(viewer):
    """Worksites the viewer may open, in any status (history stays readable)."""
    from fieldmonitoring.registry.models import Worksite

    worksites = Worksite.objects.select_related("village", "commune")
    if viewer.role in (Role.RDP, Role.ADMIN, Role.NATIONAL_SPECIALIST):
        return worksites
    if viewer.role == Role.REGIONAL_SPECIALIST:
        return worksites.filter(region_id=viewer.region_id)
    if viewer.role == Role.SC:
        return worksites.filter(commune_id=viewer.commune_id)
    return worksites.filter(assignments__user=viewer).distinct()
