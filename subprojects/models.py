from django.db import models
from src.settings import AUTH_USER_MODEL


class Contractor(models.Model):
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class BeneficiaryGroup(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Subproject(models.Model):
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
        ('canceled', 'Canceled'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    # Replacing GIS PointField with standard latitude and longitude
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)

    contractors = models.ManyToManyField(Contractor, related_name="subprojects")

    # ForeignKey to AdministrativeLevel (to be defined later)
    administrative_level = models.ForeignKey(
        'administrativelevels.AdministrativeUnit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subprojects",
    )

    # Latest progress
    latest_construction_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    latest_disbursement_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    # Many-to-Many through SubprojectBeneficiary
    beneficiary_groups = models.ManyToManyField(BeneficiaryGroup, through='SubprojectBeneficiary')

    # Custom Fields Json
    custom_fields = models.JSONField(blank=True, null=True, default=dict)
    def __str__(self):
        return self.name


class SubprojectBeneficiary(models.Model):
    subproject = models.ForeignKey(Subproject, on_delete=models.CASCADE, related_name="beneficiary_data")
    beneficiary_group = models.ForeignKey(BeneficiaryGroup, on_delete=models.CASCADE, related_name="subproject_data")
    beneficiary_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('subproject', 'beneficiary_group')  # Prevent duplicate entries

    def __str__(self):
        return f"{self.beneficiary_count} from {self.beneficiary_group.name} in {self.subproject.name}"


class ProgressUpdate(models.Model):
    subproject = models.ForeignKey(Subproject, on_delete=models.CASCADE, related_name="progress_updates")
    update_date = models.DateField(auto_now_add=True)
    construction_rate = models.DecimalField(max_digits=5, decimal_places=2)
    disbursement_rate = models.DecimalField(max_digits=5, decimal_places=2)
    updated_by = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Update on {self.update_date} for {self.subproject.name}"


class SiteVisit(models.Model):
    subproject = models.ForeignKey(Subproject, on_delete=models.CASCADE, related_name="site_visits")
    visit_date = models.DateField()
    conducted_by = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    observations = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Visit on {self.visit_date} for {self.subproject.name}"


class SiteVisitImage(models.Model):
    site_visit = models.ForeignKey(SiteVisit, on_delete=models.CASCADE, related_name="visit_images")
    image = models.ImageField(upload_to='site_visits/')
    caption = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Image for {self.site_visit.subproject.name} ({self.caption})"


class Document(models.Model):
    subproject = models.ForeignKey(Subproject, on_delete=models.CASCADE, related_name="documents")
    uploaded_by = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    file = models.FileField(upload_to='subproject_documents/')
    description = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Document for {self.subproject.name}"
