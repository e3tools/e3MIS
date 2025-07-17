# subprojects/forms.py
from django import forms
from subprojects.models import SubprojectCustomField, SubprojectCustomFieldDependency


class SubprojectCustomFieldsForm(forms.ModelForm):
    dependencies = forms.ModelMultipleChoiceField(queryset=SubprojectCustomField.objects.all(), required=False)

    class Meta:
        model = SubprojectCustomField
        fields = ['name', 'config_schema', 'dependencies']

    def save(self, commit=True):
        dependencies = list()
        dependency_objs = self.cleaned_data.pop('dependencies')
        instance = super().save(commit)
        old_dependencies = SubprojectCustomFieldDependency.objects.filter(child=instance)
        old_dependencies.delete()
        if commit:
            for dependency_obj in dependency_objs:
                dependencies.append(SubprojectCustomFieldDependency(
                    parent=dependency_obj,
                    child=instance
                ))
            SubprojectCustomFieldDependency.objects.bulk_create(dependencies)
        return instance
