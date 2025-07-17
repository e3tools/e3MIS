from django import forms
from subprojects.models import SubprojectFormResponse

class CustomForm(forms.ModelForm):
    class Meta:
        model = SubprojectFormResponse
        fields = [
            'name', 'description', 'status', 'start_date', 'end_date',
            'latitude', 'longitude'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            # 'contractors': forms.CheckboxSelectMultiple(),
            # 'beneficiary_groups': forms.CheckboxSelectMultiple(),
        }