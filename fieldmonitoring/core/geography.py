"""Field monitoring geography on top of the MIS administrative-unit tree.

Field monitoring speaks of regions, communes and villages (the SC is a *communal* supervisor).
Each programme maps those words onto its own administrative levels in ProgrammeConfig. Without
that mapping the tree position is used: village → parent commune → grandparent region.
"""
from administrativelevels.models import AdministrativeUnit


def _config():
    from .models import ProgrammeConfig

    return ProgrammeConfig.get()


def _ancestor_at_level(unit, level_id):
    node = unit
    while node is not None:
        if node.level_id == level_id:
            return node
        node = node.parent
    return None


def commune_of(unit: AdministrativeUnit) -> AdministrativeUnit:
    """The unit playing the "commune" role for ``unit`` (itself if it is one)."""
    config = _config()
    if config.commune_level_id:
        found = _ancestor_at_level(unit, config.commune_level_id)
        if found is not None:
            return found
    return unit.parent or unit


def region_of(unit: AdministrativeUnit) -> AdministrativeUnit | None:
    config = _config()
    if config.region_level_id:
        return _ancestor_at_level(unit, config.region_level_id)
    return commune_of(unit).parent


def villages_under(area: AdministrativeUnit):
    """Units that can hold a worksite inside ``area`` (a commune or a region)."""
    config = _config()
    ids = AdministrativeUnit.get_descendant_ids([area.pk])
    units = AdministrativeUnit.objects.filter(pk__in=ids).exclude(pk=area.pk)
    if config.village_level_id:
        return units.filter(level_id=config.village_level_id)
    return units.filter(children__isnull=True)
