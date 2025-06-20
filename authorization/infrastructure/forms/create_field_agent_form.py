from django import forms
from authorization.models import CustomUser


class CreateFieldAgentForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'administrative_unit']
