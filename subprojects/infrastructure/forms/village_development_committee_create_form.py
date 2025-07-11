from django import forms

from administrativelevels.models import AdministrativeUnit
from subprojects.models import VillageDevelopmentCommittee


class VillageDevelopmentCommitteeCreateForm(forms.ModelForm):
    village_neighborhood = forms.ModelChoiceField(queryset=AdministrativeUnit.objects.all(),
                                                  label='Village / Neighborhood')
    name_of_the_sales_representative = forms.CharField(label='Name of the Sales Representative')
    number_of_male_members_in_the_b_adv_adq_and_its_organs = forms.IntegerField(
        label='Number of male members in the B-ADV/ADQ and its organs')
    number_of_female_members_in_the_b_adv_adq_and_its_organs = forms.IntegerField(
        label='Number of female members in the B-ADV/ADQ and its organs')
    number_of_young_members_in_the_b_adv_adq_and_its_organs = forms.IntegerField(
        label='Number of young members in the B-ADV/ADQ and its organs')
    adv_account_number = forms.CharField(label='ADV account number')

    class Meta:
        model = VillageDevelopmentCommittee
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        qs = AdministrativeUnit.objects.filter(
            id__in=self.get_descendants(user.administrative_unit))
        self.fields['village_neighborhood'].queryset = qs

    def get_descendants(self, administrative_unit):
        descendants = list()

        def recurse(node):
            if node.children.exists():
                for child in node.children.all():
                    recurse(child)
            else:
                descendants.append(node.id)

        recurse(administrative_unit)
        return descendants
