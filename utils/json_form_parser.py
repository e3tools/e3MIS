from django import forms
from django.utils.translation import gettext as _
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from trackableobjects.models import TrackableObjectInstance
from administrativelevels.models import AdministrativeUnit
import json


class ButtonWidget(forms.widgets.Widget):
    # No value_from_datadict because we don't expect data for a button
    def __init__(self, label="Click", button_type="button", **kwargs):
        self.label = label
        self.button_type = button_type
        super().__init__(**kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        attrs_str = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        # Give it a name/value if you want to detect clicks server-side
        return mark_safe(format_html(
            '<div class="row d-none" id="geolocation-display">'
            '<div class="col-6"><b>Latitude:</b> <span class="lat-label"></span></div>'
            '<div class="col-6"><b>Longitude:</b> <span class="lon-label"></span></div>'
            '<div class="col-6"><b>Accuracy:</b> ±<span class="acc-label"></span>m</div>'
            '</div>'
            '<div class="row d-none" id="geocode-address-display">'
            '<div class="col-12"><b>Address:</b> <span class="address-label"></span></div>'
            '</div>'
            '<button type="{}" name="{}" value="1" {}>{}'
            '<i class="fas fa-spinner fa-spin ml-2 d-none" id="btn-spinner"></i>'
            '</button>',
            self.button_type, name, mark_safe(attrs_str), self.label
        ))


class ButtonField(forms.Field):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        super().__init__(*args, **kwargs)

    # Optional: treat "pressed" as True if present
    def clean(self, value):
        return bool(value)


def parse_custom_jsonschema(schema_json, page_index=0, administrative_level_ids=[]):
    form_def = schema_json['form'][page_index]
    page_schema = form_def['page']
    options = form_def.get('options', {}).get('fields', {})

    field_map = {
        'string': forms.CharField,
        'number': forms.FloatField,
        'integer': forms.IntegerField,
        'boolean': forms.BooleanField,
        'file': forms.FileField,
    }

    required_fields = set(page_schema.get('required', []))
    field_list = []  # Store fields with their order for sorting

    for field_name, field_schema in page_schema.get('properties', {}).items():
        meta = options.get(field_name, {})
        label = meta.get('label', field_name)
        help_text = meta.get('help', '')
        order = meta.get('order', 999)  # Default order if not specified

        common_args = {
            'label': label,
            'help_text': help_text,
            'required': field_name in required_fields,
        }

        # Get validators
        validators = field_schema.get('validators', {})

        # Handle dependencies (conditional display)
        dependencies = meta.get('dependencies', {})
        widget_attrs = {}

        if dependencies:
            for dep_field, dep_config in dependencies.items():
                widget_attrs['data-depends-on'] = dep_field
                widget_attrs['data-depends-operator'] = dep_config.get('operator', 'equals')
                widget_attrs['data-depends-value'] = dep_config.get('value', '')
                widget_attrs['data-conditional'] = 'true'

        field_instance = None

        # Dropdown (enum)
        if field_schema.get('type') == 'string' and 'enum' in field_schema:
            choices = [(opt, opt) for opt in field_schema['enum']]
            widget_attrs['class'] = widget_attrs.get('class', '') + ' form-control'
            field_instance = forms.ChoiceField(
                choices=choices,
                widget=forms.Select(attrs=widget_attrs),
                **common_args
            )

        # Multiselect (multi)
        elif field_schema.get('type') == 'string' and 'multi' in field_schema:
            choices = [(opt, opt) for opt in field_schema['multi']]
            widget_attrs['class'] = widget_attrs.get('class', '') + ' form-control'
            field_instance = forms.MultipleChoiceField(
                choices=choices,
                widget=forms.SelectMultiple(attrs=widget_attrs),
                **common_args
            )

        # TrackableObject
        elif field_schema.get('type') == 'trackable_object':
            administrative_level_restriction = validators.get('administrative_level_restriction', 'false')
            queryset = TrackableObjectInstance.objects.filter(
                trackable_object__id=validators.get('trackable_object_id', None)
            )
            if administrative_level_restriction == 'true':
                queryset = queryset.filter(administrative_units__id__in=administrative_level_ids)
            widget_attrs['class'] = widget_attrs.get('class', '') + ' form-control'
            field_instance = forms.ModelChoiceField(
                queryset=queryset,
                widget=forms.Select(attrs=widget_attrs),
                **common_args
            )

        # AdministrativeLevel
        elif field_schema.get('type') == 'administrative_level':
            administrative_level_restriction = validators.get('administrative_level_restriction', 'false')
            queryset = AdministrativeUnit.objects.all()
            if administrative_level_restriction == 'true':
                queryset = queryset.filter(id__in=administrative_level_ids)
            widget_attrs['class'] = widget_attrs.get('class', '') + ' form-control'
            field_instance = forms.ModelChoiceField(
                queryset=queryset,
                widget=forms.Select(attrs=widget_attrs),
                **common_args
            )
            field_instance.label_from_instance = lambda obj: obj.hierarchy_name

        # Boolean
        elif field_schema.get('type') == 'bool':
            field_instance = forms.BooleanField(
                widget=forms.CheckboxInput(attrs=widget_attrs),
                **common_args
            )

        # Date field
        elif field_schema.get('type') == 'string' and field_schema.get('format') == 'date':
            validator_min = validators.get('min', None)
            validators_max = validators.get('max', None)
            date_attrs = {
                'type': 'date',
                'class': 'form-control'
            }
            if validator_min:
                date_attrs['min'] = validator_min
            if validators_max:
                date_attrs['max'] = validators_max
            date_attrs.update(widget_attrs)

            field_instance = forms.DateField(
                widget=forms.DateInput(attrs=date_attrs),
                **common_args
            )

        elif field_schema.get('type') == 'file':
            file_attrs = {'type': 'file', 'class': 'custom-file-input'}
            file_attrs.update(widget_attrs)
            field_instance = forms.FileField(
                widget=forms.FileInput(attrs=file_attrs),
                **common_args
            )

        elif field_schema.get('type') == 'geolocation':
            field_list.append((order, 'get_geoloc', ButtonField(
                widget=ButtonWidget(
                    label=_('Use my location'),
                    attrs={"class": "btn btn-secondary btn-use-location"}
                ), **common_args
            )))
            hidden_attrs = {'class': 'coordinates'}
            hidden_attrs.update(widget_attrs)
            field_instance = forms.CharField(
                widget=forms.HiddenInput(attrs=hidden_attrs),
                **common_args
            )

        # Number with validators
        elif field_schema.get('type') in ['number', 'integer']:
            field_type = field_schema.get('type')
            field_class = field_map.get(field_type, forms.CharField)

            number_attrs = {'class': 'form-control', 'type': 'number'}
            if 'min_value' in validators:
                number_attrs['min'] = validators['min_value']
            if 'max_value' in validators:
                number_attrs['max'] = validators['max_value']
            number_attrs.update(widget_attrs)

            field_instance = field_class(
                widget=forms.NumberInput(attrs=number_attrs),
                **common_args
            )

        # String with validators
        elif field_schema.get('type') == 'string':
            text_attrs = {'class': 'form-control'}
            if 'min_length' in validators:
                text_attrs['minlength'] = validators['min_length']
            if 'max_length' in validators:
                text_attrs['maxlength'] = validators['max_length']
            text_attrs.update(widget_attrs)

            field_instance = forms.CharField(
                widget=forms.TextInput(attrs=text_attrs),
                **common_args
            )

        else:
            field_type = field_schema.get('type', 'string')
            field_class = field_map.get(field_type, forms.CharField)
            widget_attrs['class'] = widget_attrs.get('class', '') + ' form-control'
            field_instance = field_class(
                widget=forms.TextInput(attrs=widget_attrs),
                **common_args
            )

        # Add to list with order
        if field_instance:
            field_list.append((order, field_name, field_instance))

    # Sort by order and create fields dict
    field_list.sort(key=lambda x: x[0])
    fields = {field_name: field_instance for _, field_name, field_instance in field_list}

    return type(f"DynamicFormPage{page_index}", (forms.Form,), fields)
