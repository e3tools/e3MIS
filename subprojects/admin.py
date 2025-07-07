from django.contrib import admin
from subprojects.models import SubprojectCustomField, Subproject, SubprojectFormResponse


admin.site.register(SubprojectFormResponse)
admin.site.register(SubprojectCustomField)
admin.site.register(Subproject)
