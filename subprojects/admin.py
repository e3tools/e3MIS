from django.contrib import admin
from subprojects.models import SubprojectCustomField, Subproject, SubprojectFormResponse, BeneficiaryGroup


admin.site.register(SubprojectFormResponse)
admin.site.register(SubprojectCustomField)
admin.site.register(Subproject)
admin.site.register(BeneficiaryGroup)
