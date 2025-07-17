from django.contrib import admin
from .models import AdministrativeLevel, AdministrativeUnit
# Register your models here.

admin.site.register(AdministrativeLevel)
admin.site.register(AdministrativeUnit)
