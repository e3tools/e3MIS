from django import forms
from django.db import transaction
from django.db.models import Max
from django.utils.translation import gettext as _
from django.contrib.auth.models import Group
from trackableobjects.models import FollowUpEvent, FollowUpEventDependency, TrackableObject


class FollowUpEventForm(forms.ModelForm):
    name = forms.CharField(label=_("Name"), max_length=255)
    dependencies = forms.ModelMultipleChoiceField(queryset=FollowUpEvent.objects.all(), label=_('Dependencies'),
                                                  required=False)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': '4'}), label=_('Description'), required=False)
    is_one_off = forms.BooleanField(widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
                                    label=_('One time'), help_text=_(
            'Check mark to denote that the form can only have one set of responses'), required=False)
    is_active = forms.BooleanField(widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
                                   label=_('Active'), help_text=_(
            'Check mark to denote this Follow Up Event will be visible for field agents.'), required=False)
    groups = forms.ModelMultipleChoiceField(queryset=Group.objects.all(), label=_('Groups'))
    trackable_objects = forms.ModelMultipleChoiceField(queryset=TrackableObject.objects.all(),
                                                       label=_('Trackable Objects'), required=False)

    class Meta:
        model = FollowUpEvent
        fields = ['name', 'description', 'jsonForm', 'dependencies', 'groups',
                  'trackable_objects', 'is_one_off', 'is_active', 'identifier_field']

    def __init__(self, *args, **kwargs):
        self.trackable_object = TrackableObject.objects.filter(id=kwargs.pop('trackable_object', None)).first()
        self.user = kwargs.pop('user', None)
        self.creating = 'instance' not in kwargs or kwargs['instance'] is None

        super().__init__(*args, **kwargs)

        if self.trackable_object is not None:
            self.fields['trackable_objects'].initial = self.trackable_object

        # A follow-up can wait for another follow-up of the same trackable object. When editing, offer the
        # follow-ups of the objects this one is linked to and keep the saved dependencies selected;
        # otherwise saving the form would silently drop them.
        if self.trackable_object is not None:
            objects = [self.trackable_object]
        elif not self.creating:
            objects = list(self.instance.trackable_objects.all())
        else:
            objects = []
        if objects:
            qs = FollowUpEvent.objects.filter(trackable_objects__in=objects)
        else:
            qs = FollowUpEvent.objects.filter(trackable_objects=None)
        if not self.creating:
            parent_ids = list(FollowUpEventDependency.objects.filter(child=self.instance)
                              .values_list('parent_id', flat=True))
            qs = (qs | FollowUpEvent.objects.filter(pk__in=parent_ids)).exclude(pk=self.instance.pk)
            self.initial.setdefault('dependencies', parent_ids)
        self.fields['dependencies'].queryset = qs.distinct()

    def save(self, commit=True):
        dependencies = list()
        dependency_objs = self.cleaned_data.pop('dependencies')
        if self.trackable_object is not None:
            self.instance.trackable_object = self.trackable_object

        with transaction.atomic():
            if self.creating:
                self.instance.created_by = self.user
                max_order = (FollowUpEvent.objects
                    .select_for_update()
                    .aggregate(Max('order'))['order__max'] or 0)
                self.instance.order = max_order + 1

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
