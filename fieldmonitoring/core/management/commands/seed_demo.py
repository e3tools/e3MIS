"""Demo data mirroring the field monitoring reference screens. Development and demo only.

Creates a small administrative tree (Région → Commune → Village) and maps it in ProgrammeConfig,
so it should run on an empty database, not on a deployment that already has MIS data.
Demo users sign in with ``<name>@example.org``.
"""

import io
import os
import secrets
import uuid
from datetime import date, datetime, timedelta

from django.contrib.auth.models import Group
from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image

from authorization.models import DeviceClass, Role, User
from fieldmonitoring.compliance.models import Pause, RoleThreshold
from fieldmonitoring.core import clock
from fieldmonitoring.core.models import ProgrammeConfig
from administrativelevels.models import AdministrativeLevel, AdministrativeUnit
from fieldmonitoring.registry.models import Worksite, WorksiteAssignment
from fieldmonitoring.visits.models import (
    CaptureToken,
    FieldReasonCode,
    FlagKind,
    Photo,
    UnverifiedReason,
    Visit,
    VisitFlag,
    VisitStatus,
)
from fieldmonitoring.visits.photos import dhash
from fieldmonitoring.visits.state_machine import Event, apply
from fieldmonitoring.warning.services import generate

SEGUELA = (7.9611, -6.6731)


def offset(lat, lng, north_m, east_m):
    return lat + north_m / 111_320, lng + east_m / 110_500


class Command(BaseCommand):
    help = "Create demo users, worksites and six weeks of visits. Refuses to run twice."

    def add_arguments(self, parser):
        parser.add_argument("--password", help="Password for every demo user (default: $DEMO_PASSWORD)")

    @transaction.atomic
    def handle(self, *args, password=None, **options):
        if User.objects.filter(email="koffi@example.org").exists():
            raise CommandError("Demo data already exists.")
        password = password or os.environ.get("DEMO_PASSWORD")
        generated = password is None
        password = password or secrets.token_urlsafe(9)
        self.password = password
        self.config = ProgrammeConfig.get()
        self.today = clock.today(self.config)
        for role, days in RoleThreshold.LAUNCH_VALUES.items():
            RoleThreshold.objects.get_or_create(role=role, defaults={"days": days})

        self._registry()
        self._users()
        self._photo()
        self._history()
        this_monday = self.today - timedelta(days=self.today.weekday())
        for week in (this_monday - timedelta(weeks=1), this_monday):
            generate(week)

        call_command("seed_demo_forms", stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self.stdout.write("Users (<name>@example.org): admin, rdp, koffi (SC), awa (SC), amadou (FC), "
                          "ibrahim (FT), fatou (regional specialist), konan (national specialist) …")
        if generated:
            self.stdout.write(f"Password for all demo users: {password}")

    # --- registry ---------------------------------------------------------------

    def _registry(self):
        levels = {}
        for order, name in enumerate(("Région", "Commune", "Village"), start=1):
            levels[name], _ = AdministrativeLevel.objects.get_or_create(name=name, defaults={"order": order})
        self.config.region_level = levels["Région"]
        self.config.commune_level = levels["Commune"]
        self.config.village_level = levels["Village"]
        self.config.save()

        def unit(name, level, parent=None):
            return AdministrativeUnit.objects.create(name=name, level=levels[level], parent=parent)

        bere = unit("Béré", "Région")
        dabou = unit("Dabou", "Commune", bere)
        sikensi = unit("Sikensi", "Commune", bere)
        seguela = unit("Séguéla", "Village", dabou)
        bodokro = unit("Bodokro", "Village", dabou)
        tieningboue = unit("Tiéningboué", "Village", sikensi)
        kounahiri = unit("Kounahiri", "Village", sikensi)

        def site(name, code, village, north, east, high_risk=False, located=True):
            lat, lng = offset(*SEGUELA, north, east)
            return Worksite.objects.create(
                name=name,
                code=code,
                village=village,
                location=Point(lng, lat, srid=4326) if located else None,
                is_high_risk=high_risk,
                high_risk_review_due_on=self.today + timedelta(days=60) if high_risk else None,
            )

        self.w = {
            "bs02": site("Bâtiment scolaire BS-02", "BS-02", seguela, 0, 0, high_risk=True),
            "f07": site("Forage F-07", "F-07", seguela, 250, 180),
            "rs114": site("Piste rurale RS-114", "RS-114", seguela, -300, 150),
            "lp5": site("Latrines publiques LP-5", "LP-5", seguela, 0, 0, located=False),
            "bd3": site("Barrage BD-3", "BD-3", bodokro, 4200, -2600),
            "cs1": site("Centre de santé CS-1", "CS-1", bodokro, 4500, -2300),
            "mt": site("Marché de Tiéningboué", "MT-1", tieningboue, -9000, 7000),
            "pk": site("Pont de Kounahiri", "PK-1", kounahiri, 15000, 12000, high_risk=True),
            "ec4": site("École primaire EP-4", "EP-4", tieningboue, -9300, 7400),
        }
        self.communes = {"dabou": dabou, "sikensi": sikensi}
        self.region = bere

    # --- people -----------------------------------------------------------------

    def _user(self, username, full_name, role, **extra):
        user = User(
            full_name=full_name,
            role=role,
            email=f"{username}@example.org",
            onboarded_on=self.today - timedelta(days=70),
            **extra,
        )
        user.set_password(self.password)
        user.full_clean(exclude=["password"])
        user.save()
        # MIS side: forms are shown by group and administrative unit.
        if user.commune_id or user.region_id:
            user.administrative_units.add(user.commune or user.region)
        group = {Role.FT: "Technical facilitator", Role.FC: "Community facilitator"}.get(role)
        if group:
            user.groups.add(Group.objects.get_or_create(name=group)[0])
        return user

    def _users(self):
        dabou, sikensi = self.communes["dabou"], self.communes["sikensi"]
        issued = {"device_class": DeviceClass.ISSUED}
        self.admin = self._user("admin", "Administrateur", Role.ADMIN, is_staff=True, is_superuser=True)
        self.rdp = self._user("rdp", "Aïcha Koné", Role.RDP, is_staff=True)
        self.koffi = self._user("koffi", "Koffi Yao", Role.SC, commune=dabou, **issued)
        self.awa = self._user("awa", "Awa Fofana", Role.SC, commune=sikensi, **issued)
        self.seydou = self._user("seydou", "Seydou Bamba", Role.SC, commune=sikensi, **issued)
        team = lambda sc: {"supervisor": sc, "commune": sc.commune}  # noqa: E731
        self.u = {
            "ibrahim": self._user("ibrahim", "Ibrahim Traoré", Role.FT, **team(self.koffi), **issued),
            "mariam": self._user("mariam", "Mariam Coulibaly", Role.FC, **team(self.koffi)),
            "amadou": self._user("amadou", "Amadou Diallo", Role.FC, **team(self.koffi)),
            "salif": self._user("salif", "Salif Ouattara", Role.FT, **team(self.koffi), **issued),
            "aya": self._user("aya", "Aya Kouassi", Role.FC, **team(self.koffi)),
            "yacouba": self._user("yacouba", "Yacouba Sanogo", Role.FT, **team(self.koffi), **issued),
            "nathalie": self._user("nathalie", "Nathalie Békoin", Role.FC, **team(self.awa)),
        }
        self.fatou = self._user("fatou", "Fatou Ndiaye", Role.REGIONAL_SPECIALIST, region=self.region)
        self.konan = self._user("konan", "Dr Konan Assi", Role.NATIONAL_SPECIALIST)

        w = self.w
        assignments = {
            "ibrahim": ["bs02", "f07", "rs114", "bd3", "cs1", "lp5"],
            "mariam": ["f07", "rs114", "bd3", "cs1"],
            "amadou": ["bs02", "f07", "rs114", "bd3", "lp5"],
            "salif": ["bs02", "rs114", "bd3", "cs1", "lp5"],
            "aya": ["f07", "bd3", "cs1"],
            "yacouba": ["bs02", "f07", "rs114", "bd3"],
            "nathalie": ["mt", "pk", "ec4"],
        }
        for username, sites in assignments.items():
            for key in sites:
                WorksiteAssignment.objects.create(
                    user=self.u[username], worksite=w[key], assigned_on=self.today - timedelta(days=70)
                )
        Pause.objects.create(
            user=self.u["aya"],
            starts_on=self.today - timedelta(days=9),
            ends_on=self.today + timedelta(days=5),
            reason="Congé annuel",
            set_by=self.koffi,
        )

    # --- visits -----------------------------------------------------------------

    def _photo(self):
        buffer = io.BytesIO()
        Image.new("RGB", (64, 48), (120, 110, 90)).save(buffer, "JPEG")
        image = Image.open(io.BytesIO(buffer.getvalue()))
        self.photo = Photo.objects.create(
            file=ContentFile(buffer.getvalue(), name="seed.jpg"),
            size_bytes=len(buffer.getvalue()),
            perceptual_hash=dhash(image),
            uploaded_by=self.admin,
        )

    def _at(self, days_ago, hour, minute=0) -> datetime:
        return clock.at_local(
            self.today - timedelta(days=days_ago), datetime.min.time().replace(hour=hour, minute=minute),
            self.config,
        )

    def _visit(self, user, worksite, days_ago, hour=9, minutes=45, *, outcome="verified", reason=None):
        """Create a visit through the state machine, with historical server times."""
        start = self._at(days_ago, hour, 10 + (days_ago * 7) % 40)
        if worksite.location:
            lat, lng = offset(worksite.latitude, worksite.longitude, 20, -15)
            location = Point(lng, lat, srid=4326)
        else:
            location = None
        visit = Visit(
            user=user,
            worksite=worksite,
            checked_in_at=start,
            checkin_location=location,
            checkin_accuracy_m=14,
            checkin_distance_m=26 if worksite.location else None,
            capture_token=CaptureToken.objects.create(user=user, expires_at=start, photo=None),
            photo=self.photo,
            checkin_idempotency_key=str(uuid.uuid4()),
            is_mock_location=reason == UnverifiedReason.MOCK_LOCATION,
        )
        if outcome == "verified":
            apply(visit, Event.CHECK_IN_PASSED)
        else:
            if reason == UnverifiedReason.LOCATION_FAILED:
                visit.checkin_location, visit.checkin_accuracy_m, visit.checkin_distance_m = None, None, None
            apply(visit, Event.CHECK_IN_FAILED, reason=reason or UnverifiedReason.LOCATION_FAILED)
        VisitStatus.objects.create(visit=visit, works_progress="on_schedule", issue_reported=False)
        if outcome == "no_checkout":
            apply(visit, Event.AUTO_CLOSE)
        else:
            visit.checked_out_at = start + timedelta(minutes=minutes)
            visit.time_on_site_s = minutes * 60
            visit.checkout_location = location
            apply(visit, Event.CHECK_OUT)
        if reason == UnverifiedReason.MOCK_LOCATION:
            VisitFlag.objects.create(
                visit=visit, kind=FlagKind.MOCK_LOCATION, detail={"device_class": user.device_class}
            )
        return visit

    def _history(self):
        u, w = self.u, self.w
        pattern = {
            # username: (days ago of verified visits, typical minutes on site, sites)
            "ibrahim": ([19, 33, 40], 22, ["bs02", "f07", "rs114"]),
            "mariam": ([11, 15, 22, 29], 51, ["f07", "rs114", "bd3"]),
            "amadou": ([2, 5, 8, 12, 16, 19, 24, 31], 47, ["rs114", "bd3", "bs02", "lp5", "f07"]),
            "salif": ([1, 3, 4, 6, 8, 10, 12, 13, 17, 20, 23, 26, 34], 66, ["bs02", "rs114", "bd3", "cs1"]),
            "aya": ([9, 12, 16, 19, 23, 26], 38, ["f07", "bd3", "cs1"]),
            "yacouba": ([4, 6, 10, 13, 17, 20, 22, 25], 44, ["bs02", "f07", "rs114", "bd3"]),
            "nathalie": ([16, 18, 26], 35, ["mt", "ec4"]),
        }
        for username, (days, minutes, sites) in pattern.items():
            for i, d in enumerate(days):
                self._visit(u[username], w[sites[i % len(sites)]], d, minutes=minutes + (i % 3) * 5)

        # The review queue from the SC screen.
        amadou_open = self._visit(u["amadou"], w["f07"], 1, hour=14, outcome="no_checkout")
        amadou_open.field_reason_code = FieldReasonCode.BATTERY_DIED
        amadou_open.field_reason_at = clock.now()
        amadou_open.save()
        salif_fix = self._visit(u["salif"], w["bd3"], 1, hour=11, outcome="unverified",
                                reason=UnverifiedReason.LOCATION_FAILED)
        salif_fix.field_reason_code = FieldReasonCode.NO_LOCATION_FIX
        salif_fix.field_reason_at = clock.now()
        salif_fix.save()
        self._visit(u["yacouba"], w["rs114"], 2, hour=10, outcome="unverified",
                    reason=UnverifiedReason.MOCK_LOCATION)

        # Supervisors record visits too.
        for d in (3, 7, 12, 18):
            self._visit(self.koffi, w["bd3"], d, minutes=55)
        for d in (15, 22):
            self._visit(self.seydou, w["mt"], d, minutes=40)
        for d in (5, 11, 20):
            self._visit(self.awa, w["ec4"], d, minutes=50)

        # Specialists: regional last visited 8 days ago; national has three field days this month.
        for d in (8, 22, 37, 50):
            self._visit(self.fatou, w["bs02" if d == 8 else "bd3"], d, hour=10, minutes=70)
        month_days = [d for d in (6, 7, 9) if (self.today - timedelta(days=d)).month == self.today.month]
        for d in month_days or [1]:
            self._visit(self.konan, w["mt"], d, hour=10, minutes=90)
