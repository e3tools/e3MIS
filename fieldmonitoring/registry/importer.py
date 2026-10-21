"""CSV bulk import for the worksite registry (Story 1.3).

Columns: name, code, village, commune, region, latitude, longitude, tolerance_m, status.
Latitude/longitude may be blank: a null coordinate is an expected state (BR-9).
Region, commune and village are names of existing MIS administrative units (region → commune →
village, each inside the previous one). The import never creates units: load the tree first.
The high-risk flag is not importable; it goes through the BR-15 approval workflow.
"""

import csv
import io
from dataclasses import dataclass, field

from django.contrib.gis.geos import Point
from django.db import transaction

from administrativelevels.models import AdministrativeUnit

from .models import Worksite, WorksiteStatus

REQUIRED = {"name", "village", "commune", "region"}


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    errors: list[str] = field(default_factory=list)


def _unit_named(name: str, inside: AdministrativeUnit | None, what: str) -> AdministrativeUnit:
    units = AdministrativeUnit.objects.filter(name=name.strip())
    if inside is not None:
        units = units.filter(pk__in=AdministrativeUnit.get_descendant_ids([inside.pk]))
    found = list(units[:2])
    if not found:
        where = f" in {inside.name}" if inside is not None else ""
        raise ValueError(f"unknown {what} {name.strip()!r}{where}")
    if len(found) > 1:
        raise ValueError(f"{what} {name.strip()!r} is ambiguous")
    return found[0]


def _float(value):
    value = (value or "").strip().replace(",", ".")
    return float(value) if value else None


@transaction.atomic
def import_worksites(text: str) -> ImportResult:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    missing = REQUIRED - set(reader.fieldnames or [])
    result = ImportResult()
    if missing:
        result.errors.append(f"Missing columns: {', '.join(sorted(missing))}")
        return result
    for line, row in enumerate(reader, start=2):
        try:
            region = _unit_named(row["region"], None, "region")
            commune = _unit_named(row["commune"], region, "commune")
            village = _unit_named(row["village"], commune, "village")
            lat, lng = _float(row.get("latitude")), _float(row.get("longitude"))
            if (lat is None) != (lng is None):
                raise ValueError("latitude and longitude must both be set or both blank")
            status = (row.get("status") or WorksiteStatus.ACTIVE).strip() or WorksiteStatus.ACTIVE
            if status not in WorksiteStatus.values:
                raise ValueError(f"unknown status {status!r}")
            defaults = {
                "village": village,
                "commune": commune,
                "region": region,
                "location": Point(lng, lat, srid=4326) if lat is not None else None,
                "status": status,
            }
            if tolerance := (row.get("tolerance_m") or "").strip():
                defaults["tolerance_m"] = int(tolerance)
            code = (row.get("code") or "").strip()
            lookup = {"code": code} if code else {"name": row["name"].strip(), "village": village}
            _, created = Worksite.objects.update_or_create(
                **lookup, defaults={"name": row["name"].strip(), "code": code, **defaults}
            )
            result.created += created
            result.updated += not created
        except (ValueError, KeyError) as exc:
            result.errors.append(f"Line {line}: {exc}")
    if result.errors:
        transaction.set_rollback(True)
        result.created = result.updated = 0
    return result
