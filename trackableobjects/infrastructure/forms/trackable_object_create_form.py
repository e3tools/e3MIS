from django import forms
from django.utils.translation import gettext as _
from django.contrib.auth.models import Group
from trackableobjects.models import TrackableObject


class TrackableObjectForm(forms.ModelForm):
    name = forms.CharField(label=_("Name"), max_length=255)
    groups = forms.ModelMultipleChoiceField(queryset=Group.objects.all(), required=False, label=_('Groups'))
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': '4'}), label=_('Description'), required=False)

    class Meta:
        model = TrackableObject
        fields = ['name', 'description', 'jsonForm', 'groups', 'identifier_field', 'icon', 'color']
        widgets = {
            'icon': forms.HiddenInput(),
            'color': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.creating = 'instance' not in kwargs or kwargs['instance'] is None
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        groups = self.cleaned_data.pop('groups')
        if self.creating:
            self.instance.created_by = self.user
        instance = super().save(commit)
        if commit:
            instance.groups.clear()
            for group in groups:
                instance.groups.add(group)

        return instance
