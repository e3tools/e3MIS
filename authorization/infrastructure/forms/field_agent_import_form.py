from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _

MAX_FILE_SIZE = 5 * 1024 * 1024


class FieldAgentImportFileForm(forms.Form):
    file = forms.FileField(label=_('Completed template (.xlsx)'))

    def clean_file(self):
        file = self.cleaned_data['file']
        if not file.name.lower().endswith('.xlsx'):
            raise forms.ValidationError(_('Upload the .xlsx template, saved from Excel or LibreOffice.'))
        if file.size > MAX_FILE_SIZE:
            raise forms.ValidationError(_('The file is larger than 5 MB.'))
        return file


class FieldAgentImportPasswordForm(forms.Form):
    """The one password every account created by the import signs in with."""

    password1 = forms.CharField(label=_('Password'), widget=forms.PasswordInput, validators=[validate_password])
    password2 = forms.CharField(label=_('Password confirmation'), widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password1') and cleaned_data.get('password1') != cleaned_data.get('password2'):
            self.add_error('password2', _('The two password fields didn\'t match.'))
        return cleaned_data
