from django.conf import settings
from django.contrib.gis.db import models

from fieldmonitoring.core.models import UUIDModel


# Geography is the MIS administrative-unit tree (administrativelevels.AdministrativeUnit).
# Which levels play the "region", "commune" and "village" roles is programme configuration
# (ProgrammeConfig.region_level / commune_level / village_level). Villages stay labels (DEC-3).


class WorksiteStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    SUSPENDED = "suspended", "Suspended"


class Worksite(UUIDModel):
    """The unit every visit attaches to (DEC-3)."""

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=64, blank=True)
    # The unit the worksite sits in (normally a village). Commune and region are derived from it.
    village = models.ForeignKey(
        "administrativelevels.AdministrativeUnit", on_delete=models.PROTECT, related_name="worksites"
    )
    commune = models.ForeignKey(
        "administrativelevels.AdministrativeUnit", on_delete=models.PROTECT, related_name="commune_worksites"
    )
    region = models.ForeignKey(
        "administrativelevels.AdministrativeUnit", null=True, blank=True, on_delete=models.PROTECT,
        related_name="region_worksites",
    )
    # Optional links to the MIS records this worksite corresponds to (merge plan Q2).
    subproject = models.ForeignKey(
        "subprojects.Subproject", null=True, blank=True, on_delete=models.SET_NULL, related_name="worksites"
    )
    trackable_object_instance = models.ForeignKey(
        "trackableobjects.TrackableObjectInstance", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="worksites",
    )
    # Null is an expected state: no location check is possible (BR-9).
    location = models.PointField(geography=True, srid=4326, null=True, blank=True)
    tolerance_m = models.PositiveIntegerField(null=True, blank=True)
    is_high_risk = models.BooleanField(default=False)
    high_risk_review_due_on = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=WorksiteStatus.choices, default=WorksiteStatus.ACTIVE
    )
    # Created from the field ("not listed — add a worksite"); pending admin confirmation.
    is_provisional = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def latitude(self) -> float | None:
        return self.location.y if self.location else None

    @property
    def longitude(self) -> float | None:
        return self.location.x if self.location else None

    def save(self, *args, **kwargs):
        from fieldmonitoring.core.models import ProgrammeConfig

        if self.tolerance_m is None:
            self.tolerance_m = ProgrammeConfig.get().tolerance_for(self.village if self.village_id else None)
        if self.village_id and not self.commune_id:
            from fieldmonitoring.core.geography import commune_of, region_of

            self.commune = commune_of(self.village)
            self.region = region_of(self.village)
        super().save(*args, **kwargs)


class DecisionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    REJECTED = "rejected", "Rejected"


class ProvisionalCoordinate(UUIDModel):
    """A position captured under BR-9 `no_coordinate`. Not live until an admin confirms it."""

    worksite = models.ForeignKey(
        Worksite, on_delete=models.CASCADE, related_name="provisional_coordinates"
    )
    location = models.PointField(geography=True, srid=4326)
    accuracy_m = models.PositiveIntegerField(null=True, blank=True)
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    visit = models.ForeignKey(
        "visits.Visit", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    captured_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=16, choices=DecisionStatus.choices, default=DecisionStatus.PENDING
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-captured_at"]


class WorksiteAssignment(UUIDModel):
    """Unassigning is a dated end, never a delete (Story 1.4)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assignments"
    )
    worksite = models.ForeignKey(Worksite, on_delete=models.PROTECT, related_name="assignments")
    assigned_on = models.DateField()
    unassigned_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-assigned_on"]


class HighRiskFlagChange(UUIDModel):
    """BR-15 / DEC-5: proposed by the national specialist, effective only once the RdP approves."""

    worksite = models.ForeignKey(Worksite, on_delete=models.PROTECT, related_name="high_risk_changes")
    to_value = models.BooleanField()
    reason = models.TextField()
    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    proposed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=16, choices=DecisionStatus.choices, default=DecisionStatus.PENDING
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    review_due_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-proposed_at"]
