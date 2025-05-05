from subprojects.models import ProgressUpdate
from django import forms

class SubprojectProgressForm(forms.ModelForm):
    class Meta:
        model = ProgressUpdate
        fields = [
            'construction_rate', 'disbursed_amount'
        ]
