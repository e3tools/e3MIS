"""Matches the rows read by reader.py against the tree and creates what is missing.

Add only: an existing unit is recognised by its name under its parent (case and extra spaces do not
count) and never renamed, moved or deleted. The zone of a unit at the village level may change; the
radius of its worksites whose position is not confirmed yet follows.
"""
from django.db import transaction
from django.utils.translation import gettext as _

from administrativelevels.models import AdministrativeLevel, AdministrativeUnit
from administrativelevels.unit_import.reader import problem
from administrativelevels.unit_import.sheets import ZONE_HEADER, same_name

NAME_MAX_LENGTH = AdministrativeUnit._meta.get_field("name").max_length


def zone_level():
    """The level whose units carry a zone: the programme's village level, else the last level."""
    from fieldmonitoring.core.models import ProgrammeConfig

    config = ProgrammeConfig.get()
    if config.village_level_id:
        return config.village_level
    return AdministrativeLevel.objects.order_by("-order").first()


def run(rows, commit=False):
    """``(summary, errors)``. Nothing is written unless ``commit`` and there are no errors.

    ``summary``: ``levels`` (name, new and existing counts), ``new_units`` (paths), ``zones`` (units
    whose zone is set or changes) and ``radii`` (worksites whose radius follows)."""
    levels = list(AdministrativeLevel.objects.order_by("order"))
    village_level = zone_level()
    existing = {}
    zones_now = {}
    for pk, name, parent_id, zone in AdministrativeUnit.objects.values_list("pk", "name", "parent_id", "zone"):
        existing.setdefault((parent_id, same_name(name)), []).append(pk)
        zones_now[pk] = zone

    # A node is an existing unit's pk, or ("new", n) for a unit to create.
    new = {}
    seen = [set() for _level in levels]
    zones = {}
    errors = []
    for row in rows:
        node = None
        for depth, name in enumerate(row["path"]):
            level = levels[depth]
            if len(name) > NAME_MAX_LENGTH:
                errors.append(problem(row["row"], level.name, _(
                    "Too long: at most %(max)s characters."
                ) % {"max": NAME_MAX_LENGTH}))
                node = None
                break
            key = (node, same_name(name))
            matches = existing.get(key, []) if not isinstance(node, tuple) else []
            if len(matches) > 1:
                errors.append(problem(row["row"], level.name, _(
                    'Several units are named "%(name)s" here (only case or spaces differ): merge them on the '
                    'administrative units page first.'
                ) % {"name": name}))
                node = None
                break
            if matches:
                node = matches[0]
                seen[depth].add(node)
            else:
                if key not in new:
                    new[key] = {
                        "key": ("new", len(new)), "name": " ".join(name.split()), "depth": depth, "parent": node,
                        "path": row["path"][:depth + 1],
                    }
                node = new[key]["key"]
        if node is None or not row["zone"]:
            continue
        depth = len(row["path"]) - 1
        if village_level is None or levels[depth].pk != village_level.pk:
            errors.append(problem(row["row"], ZONE_HEADER, _(
                "A zone is only for a unit of the %(level)s level: leave it empty on this row."
            ) % {"level": village_level.name if village_level else "-"}))
            continue
        if zones.get(node, (row["zone"],))[0] != row["zone"]:
            errors.append(problem(row["row"], ZONE_HEADER, _(
                "Another row gives this unit a different zone (row %(row)s)."
            ) % {"row": zones[node][1]}))
            continue
        zones.setdefault(node, (row["zone"], row["row"]))

    nodes = list(new.values())
    zone_changes = {
        node: zone for node, (zone, _row) in zones.items()
        if not isinstance(node, tuple) and zones_now[node] != zone
    }
    summary = {
        "levels": [
            {"name": level.name, "new": sum(1 for n in nodes if n["depth"] == depth), "existing": len(seen[depth])}
            for depth, level in enumerate(levels)
        ],
        "new_units": [" → ".join(n["path"]) for n in nodes],
        "zones": len(zone_changes) + sum(1 for node in zones if isinstance(node, tuple)),
        "radii": _worksites_to_resize(zone_changes, commit=False),
    }
    errors.sort(key=lambda error: (error["row"] is not None, error["row"] or 0))
    if commit and not errors:
        with transaction.atomic():
            created = {}
            for n in nodes:
                parent = created[n["parent"]] if isinstance(n["parent"], tuple) else n["parent"]
                unit = AdministrativeUnit(
                    name=n["name"], level=levels[n["depth"]], parent_id=parent,
                    zone=zones.get(n["key"], ("",))[0],
                )
                unit.save()
                created[n["key"]] = unit.pk
            for zone in set(zone_changes.values()):
                AdministrativeUnit.objects.filter(
                    pk__in=[pk for pk, z in zone_changes.items() if z == zone]
                ).update(zone=zone)
            summary["radii"] = _worksites_to_resize(zone_changes, commit=True)
    return summary, errors


def _worksites_to_resize(zone_changes, commit):
    """Worksites in villages whose zone changes, without a confirmed position, whose radius differs
    from the new zone's; resized when ``commit``. Returns how many."""
    if not zone_changes:
        return 0
    from fieldmonitoring.core.models import ProgrammeConfig
    from fieldmonitoring.registry.models import Worksite

    config = ProgrammeConfig.get()
    count = 0
    for zone in set(zone_changes.values()):
        radius = config.tolerance_for(AdministrativeUnit(zone=zone))
        sites = Worksite.objects.filter(
            village_id__in=[pk for pk, z in zone_changes.items() if z == zone], location__isnull=True,
        ).exclude(tolerance_m=radius)
        count += sites.update(tolerance_m=radius) if commit else sites.count()
    return count
