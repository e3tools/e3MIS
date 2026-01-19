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
    """Simple form for adding units - only requires name"""
    class Meta:
        model = AdministrativeUnit
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Unit name'}),
        }


class AdministrativeUnitEditForm(forms.ModelForm):
    class Meta:
        model = AdministrativeUnit
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }