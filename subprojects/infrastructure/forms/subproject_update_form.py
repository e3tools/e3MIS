from django import forms
from subprojects.models import Subproject

class SubprojectForm(forms.ModelForm):
    class Meta:
        model = Subproject
        fields = [
            'name', 'description', 'status'
        ]
        # widgets = {
        #     'start_date': forms.DateInput(attrs={'type': 'date'}),
        #     'end_date': forms.DateInput(attrs={'type': 'date'}),
        #     'contractors': forms.CheckboxSelectMultiple(),
        #     'beneficiary_groups': forms.CheckboxSelectMultiple(),
        # }