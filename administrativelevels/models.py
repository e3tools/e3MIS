from django.db import models


class AdministrativeLevel(models.Model):
    """Defines hierarchical administrative levels like Country, Region, District"""

    name = models.CharField(max_length=100, unique=True)
    order = models.PositiveIntegerField(help_text="Defines the level in hierarchy (e.g., 1 for Country, 2 for Region)", unique=True)

    class Meta:
        ordering = ['order']
        unique_together = ('name', 'order')

    def __str__(self):
        return self.name


class AdministrativeUnit(models.Model):
    """Represents an administrative division (e.g., Ghana, Accra Region, etc.)"""

    name = models.CharField(max_length=200)
    level = models.ForeignKey(AdministrativeLevel, on_delete=models.CASCADE, related_name="units")
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name="children")

    class Meta:
        unique_together = ('name', 'level', 'parent')

    def __str__(self):
        return f"{self.name} ({self.level.name})"
