from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _

from authorization.models import CustomUser, Role
from fieldmonitoring.core.geography import communes, regions

# Roles that use the field app; the others (RdP, admin) are not field agents and are set in the admin.
FIELD_AGENT_ROLES = [Role.FT, Role.FC, Role.SC, Role.REGIONAL_SPECIALIST, Role.NATIONAL_SPECIALIST]
# The MIS groups that carry each facilitator's forms (same names as migration 0011). Picking the role
# pre-selects the group on the page; the admin can still change the groups.
ROLE_GROUPS = {Role.FT: 'Technical facilitator', Role.FC: 'Community facilitator'}


class SupervisorChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj} ({obj.commune.name})" if obj.commune_id else str(obj)


class CreateFieldAgentForm(forms.ModelForm):
    password1 = forms.CharField(
        label=_('Password'),
        widget=forms.PasswordInput,
        required=False,
        validators=[validate_password],
    )
    password2 = forms.CharField(
        label=_('Password confirmation'),
        widget=forms.PasswordInput,
        required=False,
    )
    role = forms.ChoiceField(
        label=_('Role'),
        choices=[('', '---------')] + [(r.value, r.label) for r in FIELD_AGENT_ROLES],
        required=False,
    )
    supervisor = SupervisorChoiceField(
        label=_('Supervisor'),
        queryset=CustomUser.objects.none(),
        required=False,
        help_text=_('The communal supervisor (SC) of a technical or community facilitator.'),
    )
    commune = forms.ModelChoiceField(label=_('Commune'), queryset=None, required=False)
    region = forms.ModelChoiceField(label=_('Region'), queryset=None, required=False)

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'administrative_units', 'groups',
                  'role', 'supervisor', 'commune', 'region']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['password1'].required = True
            self.fields['password2'].required = True
        # A new agent needs a role. Older MIS agents without one can still be edited.
        if not self.instance.pk or self.instance.role:
            self.fields['role'].required = True
        self.fields['supervisor'].queryset = (
            CustomUser.objects.filter(role=Role.SC).exclude(pk=self.instance.pk).select_related('commune')
        )
        self.fields['commune'].queryset = communes().order_by('name')
        self.fields['region'].queryset = regions().order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 or password2:
            if password1 != password2:
                self.add_error('password2', _('The two password fields didn\'t match.'))
        # Fields the role does not use are cleared, so a role change leaves nothing stale behind.
        role = cleaned_data.get('role')
        if role not in (Role.FT, Role.FC):
            cleaned_data['supervisor'] = None
        if role not in (Role.FT, Role.FC, Role.SC):
            cleaned_data['commune'] = None
        if role != Role.REGIONAL_SPECIALIST:
            cleaned_data['region'] = None
        return cleaned_data

    def save(self, commit=True):
        self.instance.is_field_agent = True
        password = self.cleaned_data.get('password1')
        if password:
            self.instance.set_password(password)
        return super().save(commit=commit)
