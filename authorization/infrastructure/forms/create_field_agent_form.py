from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _

from authorization import hierarchy
from authorization.models import CustomUser, GroupRole, Role

# Roles that use the field app; the others (RdP, admin) are not field agents and are set in the admin.
FIELD_AGENT_ROLES = [Role.FT, Role.FC, Role.SC, Role.REGIONAL_SPECIALIST, Role.NATIONAL_SPECIALIST]
# Roles attached to exactly one administrative unit, from which commune or region is derived
# (authorization/hierarchy.py). A national specialist needs none.
UNIT_ROLES = [Role.FT, Role.FC, Role.SC, Role.REGIONAL_SPECIALIST]


class SupervisorChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj} ({obj.commune.name})" if obj.commune_id else str(obj)


class CreateFieldAgentForm(forms.ModelForm):
    """A field agent is created with a role and one administrative unit (Brice, 29 Oct 2026): the
    commune or region, and the supervisor, follow from them. The supervisor is only picked when
    the commune has several SCs."""

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
    # Required for new agents, checked in clean() so a group's default role can fill it.
    role = forms.ChoiceField(
        label=_('Role'),
        choices=[('', '---------')] + [(r.value, r.label) for r in FIELD_AGENT_ROLES],
        required=False,
    )
    supervisor = SupervisorChoiceField(
        label=_('Supervisor'),
        queryset=CustomUser.objects.none(),
        required=False,
    )

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'administrative_units', 'groups',
                  'role', 'supervisor']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['password1'].required = True
            self.fields['password2'].required = True
        self.fields['supervisor'].queryset = (
            CustomUser.objects.filter(role=Role.SC).exclude(pk=self.instance.pk).select_related('commune')
        )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 or password2:
            if password1 != password2:
                self.add_error('password2', _('The two password fields didn\'t match.'))

        role = cleaned_data.get('role')
        if not role:
            # A group with a default role gives it (only when the chosen groups agree on one).
            groups = cleaned_data.get('groups') or []
            roles = set(GroupRole.objects.filter(group__in=groups).values_list('role', flat=True))
            if len(roles) == 1 and roles <= {r.value for r in FIELD_AGENT_ROLES}:
                role = cleaned_data['role'] = roles.pop()
        # A new agent needs a role. Older MIS agents without one can still be edited.
        if not role:
            if not self.instance.pk or self.instance.role:
                self.add_error('role', _('This field is required.'))
            return cleaned_data

        commune = region = supervisor = None
        units = list(cleaned_data.get('administrative_units') or [])
        if role in UNIT_ROLES:
            if len(units) != 1:
                self.add_error('administrative_units', _(
                    'Choose one administrative unit: the commune (the département for a regional specialist).'
                ))
                return cleaned_data
            commune, region = hierarchy.scope_for(role, units[0])
            if role == Role.REGIONAL_SPECIALIST and region is None:
                self.add_error('administrative_units', _('A regional specialist is attached to a département.'))
                return cleaned_data
            if role != Role.REGIONAL_SPECIALIST and commune is None:
                self.add_error('administrative_units', _('Choose a commune, or a unit inside one.'))
                return cleaned_data

        if role in (Role.FT, Role.FC):
            supervisor, candidates = hierarchy.supervisor_for(self.instance, commune)
            picked = cleaned_data.get('supervisor')
            if len(candidates) > 1:
                if picked in candidates:
                    supervisor = picked
                else:
                    self.add_error('supervisor', _('This commune has several SCs: choose the supervisor.'))
        # The model's hierarchy rules (CustomUser.clean) run on these values.
        cleaned_data['supervisor'] = supervisor
        self.instance.commune = commune
        self.instance.region = region
        return cleaned_data

    def _update_errors(self, errors):
        # Commune and region come from the unit: the model's errors on them belong to the unit
        # field (once; clean() may already have said what is wrong with the unit).
        if hasattr(errors, 'error_dict'):
            for name in ('commune', 'region'):
                messages = errors.error_dict.pop(name, [])
                if messages and 'administrative_units' not in self.errors:
                    errors.error_dict.setdefault('administrative_units', []).extend(messages)
        super()._update_errors(errors)

    def save(self, commit=True):
        self.instance.is_field_agent = True
        password = self.cleaned_data.get('password1')
        if password:
            self.instance.set_password(password)
        user = super().save(commit=commit)
        if commit:
            hierarchy.sync_team(user)
        return user
