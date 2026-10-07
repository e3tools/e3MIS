"""Import the urban/rural status of villages from a spreadsheet (.xlsx or .csv).

The zone sets the check-in radius of worksites in the village (ProgrammeConfig.urban_tolerance_m /
rural_tolerance_m). Columns are found by header name; villages are matched by name, and by their
parent's name when ``--parent-column`` is given (several villages share a name). Nothing is
written with ``--dry-run``; unmatched and ambiguous rows are always listed.

    manage.py import_village_zones zones.xlsx --village-column Village --zone-column Zone \\
        --parent-column Arrondissement --update-worksites
"""
import csv
import unicodedata
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from administrativelevels.models import RURAL, URBAN, AdministrativeUnit


def _norm(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return " ".join(text.lower().replace("-", " ").replace("'", " ").split())


def zone_of(value) -> str | None:
    text = _norm(value)
    if text.startswith("urb"):
        return URBAN
    if text.startswith("rur"):
        return RURAL
    return None


def read_rows(path: Path) -> list[dict]:
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl

        sheet = openpyxl.load_workbook(path, read_only=True, data_only=True).active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return []
        header = [str(h or "").strip() for h in rows[0]]
        return [dict(zip(header, row)) for row in rows[1:] if any(c not in (None, "") for c in row)]
    with path.open(newline="", encoding="utf-8-sig") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        return list(csv.DictReader(handle, dialect=dialect))


class Command(BaseCommand):
    help = "Set villages' urban/rural zone from a spreadsheet."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--village-column", default="Village")
        parser.add_argument("--zone-column", default="Zone")
        parser.add_argument("--parent-column", help="Column with the parent unit's name, to tell villages apart.")
        parser.add_argument("--update-worksites", action="store_true",
                            help="Also reset the check-in radius of the worksites in these villages.")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            raise CommandError(f"No file at {path}")
        rows = read_rows(path)
        village_col, zone_col, parent_col = options["village_column"], options["zone_column"], options["parent_column"]
        if rows and (village_col not in rows[0] or zone_col not in rows[0]):
            raise CommandError(f"Columns found: {', '.join(rows[0])}. Use --village-column / --zone-column.")

        by_name: dict[str, list[AdministrativeUnit]] = {}
        for unit in AdministrativeUnit.objects.select_related("parent"):
            by_name.setdefault(_norm(unit.name), []).append(unit)

        updates, unmatched, ambiguous, bad_zone = {}, [], [], []
        for number, row in enumerate(rows, start=2):
            name, zone = row.get(village_col), zone_of(row.get(zone_col))
            if zone is None:
                bad_zone.append(f"line {number}: {name!r} zone {row.get(zone_col)!r}")
                continue
            candidates = [u for u in by_name.get(_norm(name), []) if not u.children.exists()] or by_name.get(
                _norm(name), []
            )
            if parent_col and len(candidates) > 1:
                parent = _norm(row.get(parent_col))
                candidates = [u for u in candidates if u.parent and _norm(u.parent.name) == parent]
            if not candidates:
                unmatched.append(f"line {number}: {name!r}")
            elif len(candidates) > 1:
                ambiguous.append(f"line {number}: {name!r} ({len(candidates)} units)")
            else:
                updates[candidates[0].pk] = zone

        with transaction.atomic():
            changed = 0
            for zone in (URBAN, RURAL):
                ids = [pk for pk, z in updates.items() if z == zone]
                changed += AdministrativeUnit.objects.filter(pk__in=ids).exclude(zone=zone).update(zone=zone)
            moved = 0
            if options["update_worksites"]:
                from fieldmonitoring.core.models import ProgrammeConfig
                from fieldmonitoring.registry.models import Worksite

                config = ProgrammeConfig.get()
                for zone in (URBAN, RURAL):
                    ids = [pk for pk, z in updates.items() if z == zone]
                    radius = config.urban_tolerance_m if zone == URBAN else config.rural_tolerance_m
                    moved += Worksite.objects.filter(village_id__in=ids).exclude(tolerance_m=radius).update(
                        tolerance_m=radius
                    )
            if options["dry_run"]:
                transaction.set_rollback(True)

        prefix = "[dry run] " if options["dry_run"] else ""
        self.stdout.write(f"{prefix}{len(updates)} villages matched, {changed} zones changed, {moved} worksite radii reset.")
        for title, items in (("Not found", unmatched), ("Ambiguous", ambiguous), ("Unknown zone", bad_zone)):
            if items:
                self.stdout.write(f"{title} ({len(items)}):")
                for item in items[:50]:
                    self.stdout.write(f"  {item}")
                if len(items) > 50:
                    self.stdout.write(f"  … and {len(items) - 50} more")
