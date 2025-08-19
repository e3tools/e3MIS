from django import forms
from trackableobjects.models import FollowUpEvent, FollowUpEventDependency, TrackableObject


class FollowUpEventForm(forms.ModelForm):
    dependencies = forms.ModelMultipleChoiceField(queryset=FollowUpEvent.objects.all(), required=False)

    class Meta:
        model = FollowUpEvent
        fields = ['name', 'description', 'jsonForm', 'dependencies']

    def __init__(self, *args, **kwargs):
        self.trackable_object = TrackableObject.objects.filter(id=kwargs.pop('trackable_object', None)).first()
        self.user = kwargs.pop('user', None)
        self.creating = 'instance' not in kwargs or kwargs['instance'] is None
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        dependencies = list()
        dependency_objs = self.cleaned_data.pop('dependencies')
        if self.trackable_object is not None:
            self.instance.trackable_object = self.trackable_object
        if self.creating:
            self.instance.created_by = self.user
        instance = super().save(commit)
        if commit:
            old_dependencies = FollowUpEventDependency.objects.filter(child=instance)
            old_dependencies.delete()
            for dependency_obj in dependency_objs:
                dependencies.append(FollowUpEventDependency(
                    parent=dependency_obj,
                    child=instance
                ))
            FollowUpEventDependency.objects.bulk_create(dependencies)

        return instance
