"""Forms of the cycle designer: template, phase, activity, task and the forms a task needs."""
from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from authorization.models import Role
from cdd import designer
from cdd.models import Activity, CycleTemplate, Phase, Task, TaskForm
from trackableobjects.models import FollowUpEvent, TrackableObject


class CycleTemplateForm(forms.ModelForm):
    class Meta:
        model = CycleTemplate
        fields = ["name", "description", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class PhaseForm(forms.ModelForm):
    class Meta:
        model = Phase
        fields = ["name", "description", "planned_days"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ["name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class TaskEditForm(forms.ModelForm):
    completer_roles = forms.MultipleChoiceField(
        label=_("Who may mark it"), required=False, choices=Role.choices, widget=forms.CheckboxSelectMultiple,
        help_text=_("Empty: any facilitator of the cycle."),
    )

    class Meta:
        model = Task
        fields = ["name", "key", "kind", "required", "planned_offset_days", "depends_on", "instructions",
                  "completer_roles"]
        labels = {"depends_on": _("Starts after")}
        help_texts = {
            "key": _("Stable code of the task. Empty: made from the name. Fixed once a cycle follows the template."),
            "required": _("Optional tasks do not count for progress."),
            "depends_on": _("Doing the task earlier gives a warning, never a block."),
        }
        widgets = {"instructions": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, template, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = template
        others = template.tasks().select_related("activity__phase")
        if self.instance.pk:
            others = others.exclude(pk=self.instance.pk)
        self.fields["depends_on"].queryset = others
        self.fields["depends_on"].widget.attrs["class"] = "select2"
        self.fields["key"].required = False
        if self.instance.pk and designer.keys_locked(template):
            self.fields["key"].disabled = True

    def clean_key(self):
        key = self.cleaned_data.get("key")
        if self.fields["key"].disabled:
            return self.instance.key
        if not key:
            return designer.new_key(self.template, self.cleaned_data.get("name") or "")
        clash = self.template.tasks().filter(key=key)
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(_("Another task of this cycle already uses this key."))
        return key

    def clean_depends_on(self):
        depends_on = self.cleaned_data.get("depends_on")
        if depends_on and designer.loops_back(self.instance, depends_on):
            raise forms.ValidationError(_("This would make the task wait for itself."))
        return depends_on


def form_choices():
    return [
        (_("Record types"), [(f"to:{pk}", name) for pk, name in TrackableObject.objects.values_list("pk", "name")]),
        (_("Follow-up events"), [
            (f"fe:{pk}", name) for pk, name in FollowUpEvent.objects.order_by("order", "name").values_list("pk", "name")
        ]),
    ]


class TaskFormForm(forms.ModelForm):
    """One form a task needs; ``form`` picks a record type (``to:<id>``) or a follow-up event (``fe:<id>``)."""

    form = forms.ChoiceField(label=_("Form"))

    class Meta:
        model = TaskForm
        fields = ["min_count", "required"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["form"].choices = [("", "---------")] + form_choices()
        if self.instance.pk:
            self.initial["form"] = self.instance.ref

    def clean(self):
        cleaned = super().clean()
        ref = cleaned.get("form") or ""
        kind, _sep, pk = ref.partition(":")
        self.instance.trackable_object = TrackableObject.objects.filter(pk=pk).first() if kind == "to" else None
        self.instance.follow_up_event = FollowUpEvent.objects.filter(pk=pk).first() if kind == "fe" else None
        if ref and not (self.instance.trackable_object or self.instance.follow_up_event):
            self.add_error("form", _("Pick a form."))
        return cleaned


TaskFormFormSet = inlineformset_factory(Task, TaskForm, form=TaskFormForm, extra=1, can_delete=True)
