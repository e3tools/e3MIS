from django import forms

from subprojects.models import Contractor, Subproject


class ContractorCreateForm(forms.ModelForm):
    subproject = forms.ModelChoiceField(queryset=Subproject.objects.all())

    class Meta:
        model = Contractor
        fields = '__all__'

    def save(self, commit=True):
        try:
            instance = Contractor.objects.get(name=self.cleaned_data['name'])
        except Contractor.DoesNotExist:
            instance = super().save(commit)
        subproject = self.cleaned_data['subproject']
        subproject.contractors.add(instance)
        return instance


class ContractorMobileCreateForm(forms.ModelForm):

    class Meta:
        model = Contractor
        exclude = ('subproject', )

