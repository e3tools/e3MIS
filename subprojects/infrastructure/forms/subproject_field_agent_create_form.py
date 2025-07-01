from django import forms
from django.utils.translation import gettext as _

from subprojects.models import Subproject
from administrativelevels.models import AdministrativeUnit


class SubprojectFieldAgentCreateForm(forms.ModelForm):
    is_for_multiple_communities = forms.BooleanField(required=False)
    other_administrative_levels = forms.ModelMultipleChoiceField(queryset=AdministrativeUnit.objects.all(), required=False)  # TODO: filter for levels below
    name = forms.CharField(label=_('Title'))
    objective = forms.CharField(label=_('Objective'))
    description = forms.CharField(label=_('Description'))
    estimate_cost = forms.DecimalField(label=_('Estimate Cost'), widget=forms.NumberInput(attrs={'min': '0'}))
    community_grant_agreement_reference = forms.CharField(label=_('Community Grant Agreement Reference'))
    # activity_sector = forms.CharField(label=_('Activity Sector'))
    # sub_component = forms.CharField(label=_('Sub Component'))
    # type = forms.CharField(label=_('Type'))
    # project_management = forms.CharField(label=_('Project Management'))

    class Meta:
        model = Subproject
        fields = [
            'administrative_level', 'other_administrative_levels', 'is_for_multiple_communities', 'name', 'objective',
            'description', 'activity_sector', 'estimate_cost', 'community_grant_agreement_reference', 'sub_component',
            'type', 'project_management',
        ]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['administrative_level'].queryset = AdministrativeUnit.objects.all()
            self.fields['administrative_level'].initial = user.administrative_unit

