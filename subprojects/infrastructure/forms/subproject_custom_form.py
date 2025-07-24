# subprojects/forms.py
from django import forms
from django.contrib.auth.models import Group
from subprojects.models import SubprojectCustomField, SubprojectCustomFieldDependency


class SubprojectCustomFieldsForm(forms.ModelForm):
    dependencies = forms.ModelMultipleChoiceField(queryset=SubprojectCustomField.objects.all(), required=False)
    groups = forms.ModelMultipleChoiceField(queryset=Group.objects.all(), required=False)

    class Meta:
        model = SubprojectCustomField
        fields = ['name', 'config_schema', 'groups', 'dependencies']

    def save(self, commit=True):
        dependencies = list()
        dependency_objs = self.cleaned_data.pop('dependencies')
        groups = self.cleaned_data.pop('groups')
        instance = super().save(commit)
        if commit:
            old_dependencies = SubprojectCustomFieldDependency.objects.filter(child=instance)
            old_dependencies.delete()
            instance.groups.clear()
            for dependency_obj in dependency_objs:
                dependencies.append(SubprojectCustomFieldDependency(
                    parent=dependency_obj,
                    child=instance
                ))
            SubprojectCustomFieldDependency.objects.bulk_create(dependencies)
            for group in groups:
                instance.groups.add(group)

        return instance
