from django import forms
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _

from authorization.models import GroupRole, Role


class GroupForm(forms.ModelForm):
    # Pre-fills the role of users added to the group on the field-agents page.
    role = forms.ChoiceField(
        label=_('Default role'),
        choices=[('', '---------')] + list(Role.choices),
        required=False,
        help_text=_('Users added to this group get this role by default. It can still be changed per user.'),
    )

    class Meta:
        model = Group
        fields = ['name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            field_role = GroupRole.objects.filter(group=self.instance).first()
            self.initial.setdefault('role', field_role.role if field_role else '')

    def save(self, commit=True):
        group = super().save(commit=commit)
        role = self.cleaned_data.get('role')
        if role:
            GroupRole.objects.update_or_create(group=group, defaults={'role': role})
        else:
            GroupRole.objects.filter(group=group).delete()
        return group
