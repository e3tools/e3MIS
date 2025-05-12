# subprojects/forms.py
from django import forms
from subprojects.models import SubprojectCustomField

class SubprojectCustomFieldsForm(forms.ModelForm):
    class Meta:
        model = SubprojectCustomField
        fields = ['name', 'config_schema']