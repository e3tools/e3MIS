from django import forms
from django.contrib.auth.models import Group
from trackableobjects.models import TrackableObject


class TrackableObjectForm(forms.ModelForm):
    groups = forms.ModelMultipleChoiceField(queryset=Group.objects.all(), required=False)

    class Meta:
        model = TrackableObject
        fields = ['name', 'description', 'jsonForm', 'groups']

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
