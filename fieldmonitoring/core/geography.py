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


def communes():
    """Units that play the "commune" role (the units an SC, FT or FC is attached to)."""
    config = _config()
    if config.commune_level_id:
        return AdministrativeUnit.objects.filter(level_id=config.commune_level_id)
    # Tree position: the parents of villages (leaves).
    return AdministrativeUnit.objects.filter(children__isnull=False, children__children__isnull=True).distinct()


def regions():
    """Units that play the "region" role (the area of a regional specialist)."""
    config = _config()
    if config.region_level_id:
        return AdministrativeUnit.objects.filter(level_id=config.region_level_id)
    return AdministrativeUnit.objects.filter(pk__in=communes().values("parent_id"))


def _climb_to(unit, candidates):
    node = unit
    while node is not None:
        if candidates.filter(pk=node.pk).exists():
            return node
        node = node.parent
    return None


def commune_containing(unit: AdministrativeUnit) -> AdministrativeUnit | None:
    """The commune ``unit`` is (or lies in); None for a unit above the commune level."""
    return _climb_to(unit, communes())


def region_containing(unit: AdministrativeUnit) -> AdministrativeUnit | None:
    """The region ``unit`` is (or lies in); None for a unit above the region level."""
    return _climb_to(unit, regions())


def levels_configured() -> bool:
    config = _config()
    return bool(config.region_level_id and config.commune_level_id and config.village_level_id)
