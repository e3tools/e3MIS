from django.db import models
from django.utils.translation import gettext as _
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


class VillageDevelopmentCommittee(models.Model):
    village_neighborhood = models.CharField(max_length=255)
    name_of_the_sales_representative = models.CharField(max_length=255)
    number_of_male_members_in_the_b_adv_adq_and_its_organs = models.IntegerField()
    number_of_female_members_in_the_b_adv_adq_and_its_organs = models.IntegerField()
    number_of_young_members_in_the_b_adv_adq_and_its_organs = models.IntegerField()
    adv_account_number = models.CharField(max_length=255)


class Subproject(models.Model):
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
        ('canceled', 'Canceled'),
    ]

    ACTIVITY_CHOICES = [
        ('agropastoralism', _('Agropastoralism')),
        ('local_economy', _('Local economy')),
        ('sports_and_leisure', _('Sports and leisure')),
        ('connectivity', _('Connectivity')),
        ('agropastoralism', _('Agropastoralism')),
        ('water_access', _('Water access')),
        ('education', _('Education')),
        ('public_health', _('Public health')),
        ('hygiene_and_sanitation', _('Hygiene and sanitation')),
        ('public_lighting', _('Public lighting')),
        ('drinking_water_access', _('Drinking water access')),
    ]

    SUBCOMPONENT_CHOICES = [
        ('1.1', '1.1'),
        ('1.2a', '1.2a'),
        ('1.2b', '1.2b'),
        ('1.3', '1.3'),
    ]

    TYPE_CHOICES = [
        ('infrastructure', _('Infrastructure')),
        ('support_to_gie', _('Support to GIE')),
        ('infrastructure_and_support_to_gie', _('Infrastructure & Support to GIE')),
    ]

    MANAGEMENT_CHOICES = [
        ('MOC', 'MOC'),
        ('MODC', 'MODC')
    ]

    external_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    objective = models.TextField(blank=True, null=True)
    activity_sector = models.CharField(max_length=50, choices=ACTIVITY_CHOICES, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    estimate_cost = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    community_grant_agreement_reference = models.CharField(max_length=255, blank=True, null=True)

    # Replacing GIS PointField with standard latitude and longitude
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)

    contractors = models.ManyToManyField(Contractor, related_name="subprojects")
    sub_component = models.CharField(choices=SUBCOMPONENT_CHOICES, max_length=255, blank=True, null=True)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, blank=True, null=True)
    project_management = models.CharField(max_length=15, choices=MANAGEMENT_CHOICES, blank=True, null=True)

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
    latest_disbursement_rate = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    # Many-to-Many through SubprojectBeneficiary
    beneficiary_groups = models.ManyToManyField(BeneficiaryGroup, through='SubprojectBeneficiary')

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
    disbursed_amount = models.DecimalField(max_digits=15, decimal_places=2)
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


class SubprojectCustomField(models.Model):
    name = models.CharField(max_length=255)
    config_schema = models.JSONField(help_text="JSON schema + options for the form", default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class SubprojectCustomFieldDependency(models.Model):
    parent = models.ForeignKey(SubprojectCustomField, on_delete=models.CASCADE, related_name="dependencies_parents")
    child = models.ForeignKey(SubprojectCustomField, on_delete=models.CASCADE, related_name="dependencies_children")


class SubprojectFormResponse(models.Model):
    custom_form = models.ForeignKey(SubprojectCustomField, on_delete=models.CASCADE)
    subproject = models.ForeignKey(Subproject, related_name="custom_fields_responses", on_delete=models.CASCADE, null=True, blank=True)
    filled_by = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    response_schema = models.JSONField(help_text="JSON response schema", default=list)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
