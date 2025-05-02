from django import forms
from subprojects.models import Subproject

class SubprojectForm(forms.ModelForm):
    class Meta:
        model = Subproject
        fields = [
            'name', 'description', 'status', 'start_date', 'end_date',
            'latitude', 'longitude', 'contractors', 'administrative_level',
            'latest_construction_rate', 'latest_disbursement_rate', 'beneficiary_groups'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'contractors': forms.CheckboxSelectMultiple(),
            'beneficiary_groups': forms.CheckboxSelectMultiple(),
        }