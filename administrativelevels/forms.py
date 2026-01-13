from django import forms
from administrativelevels.models import AdministrativeLevel, AdministrativeUnit


class AdministrativeLevelForm(forms.ModelForm):
    class Meta:
        model = AdministrativeLevel
        fields = ['name', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class AdministrativeUnitForm(forms.ModelForm):
    class Meta:
        model = AdministrativeUnit
        fields = ['name', 'level', 'parent']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'level': forms.Select(attrs={'class': 'form-control'}),
            'parent': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        parent_unit = kwargs.pop('parent_unit', None)
        super().__init__(*args, **kwargs)

        if parent_unit:
            # When adding a child, set parent and filter levels to show only the next level
            self.fields['parent'].initial = parent_unit
            self.fields['parent'].widget = forms.HiddenInput()

            # Get the next level in hierarchy
            parent_level_order = parent_unit.level.order
            next_levels = AdministrativeLevel.objects.filter(order=parent_level_order + 1)
            self.fields['level'].queryset = next_levels

            if next_levels.count() == 1:
                self.fields['level'].initial = next_levels.first()


class AdministrativeUnitEditForm(forms.ModelForm):
    class Meta:
        model = AdministrativeUnit
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }