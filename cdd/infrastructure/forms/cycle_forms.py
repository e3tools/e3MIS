"""Forms of the "Cycles per community" pages."""
from django import forms
from django.utils.translation import gettext_lazy as _

from authorization.models import CustomUser, Role
from cdd.models import CycleStatus, CycleTemplate
from fieldmonitoring.core import clock
from fieldmonitoring.core.geography import communes


def facilitators():
    return CustomUser.objects.filter(role__in=[Role.FT, Role.FC], is_active=True).order_by("full_name", "email")


class FacilitatorChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, user):
        commune = f" · {user.commune.name}" if user.commune_id else ""
        return f"{user} ({user.role.upper() or '-'}{commune})"


class CycleStartForm(forms.Form):
    template = forms.ModelChoiceField(label=_("Cycle"), queryset=CycleTemplate.objects.filter(is_active=True))
    commune = forms.ModelChoiceField(label=_("Commune"), queryset=None)
    communities = forms.MultipleChoiceField(label=_("Communities"), widget=forms.CheckboxSelectMultiple)
    started_on = forms.DateField(label=_("Started on"), widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    planned_end = forms.DateField(label=_("Planned end"), required=False,
                                  widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    with_attached = forms.BooleanField(
        label=_("Assign the FT and FC attached to each community"), required=False, initial=True,
        help_text=_("Facilitators whose administrative unit is the community or a unit above it."),
    )
    facilitators = FacilitatorChoiceField(
        label=_("Other facilitators"), required=False, queryset=CustomUser.objects.none(),
        help_text=_("Added to every cycle started."),
    )

    def __init__(self, *args, community_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["commune"].queryset = communes().order_by("name")
        self.fields["communities"].choices = community_choices
        self.fields["facilitators"].queryset = facilitators()
        self.fields["facilitators"].widget.attrs["class"] = "select2"
        self.fields["started_on"].initial = clock.today()
        templates = self.fields["template"].queryset
        if templates.count() == 1:
            self.fields["template"].initial = templates.get()

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("started_on"), cleaned.get("planned_end")
        if start and end and end < start:
            self.add_error("planned_end", _("The planned end is before the start."))
        return cleaned


class CycleStatusForm(forms.Form):
    status = forms.ChoiceField(choices=CycleStatus.choices)
    note = forms.CharField(label=_("Reason"), widget=forms.Textarea(attrs={"rows": 2}))


class CycleFacilitatorsForm(forms.Form):
    facilitators = FacilitatorChoiceField(label=_("Facilitators"), required=False, queryset=CustomUser.objects.none())

    def __init__(self, *args, current=(), **kwargs):
        super().__init__(*args, **kwargs)
        # Keep facilitators already on the cycle even if their role changed since.
        ids = set(facilitators().values_list("pk", flat=True)) | {user.pk for user in current}
        self.fields["facilitators"].queryset = CustomUser.objects.filter(pk__in=ids).order_by("full_name", "email")
        self.fields["facilitators"].widget.attrs["class"] = "select2"
