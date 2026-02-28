from django import forms
from authorization.models import CustomUser


class CreateFieldAgentForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'administrative_units', 'groups']

    def save(self, commit=True):
        super().save(False)
        self.instance.is_field_agent = True
        return super().save(commit=commit)
