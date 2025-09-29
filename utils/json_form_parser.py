from django import forms
from django.utils.translation import gettext as _
from django.utils.html import format_html
from django.utils.safestring import mark_safe


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


def parse_custom_jsonschema(schema_json, page_index=0):
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

    fields = {}
    required_fields = set(page_schema.get('required', []))

    for field_name, field_schema in page_schema.get('properties', {}).items():
        meta = options.get(field_name, {})
        label = meta.get('label', field_name)
        help_text = meta.get('help', '')
        common_args = {
            'label': label,
            'help_text': help_text,
            'required': field_name in required_fields,
        }

        common_args.update(field_schema.get('validators', {}))

        # Dropdown (enum)
        if field_schema.get('type') == 'string' and 'enum' in field_schema:
            choices = [(opt, opt) for opt in field_schema['enum']]
            fields[field_name] = forms.ChoiceField(choices=choices, **common_args)

        # Multiselect (multi)
        if field_schema.get('type') == 'string' and 'multi' in field_schema:
            choices = [(opt, opt) for opt in field_schema['multi']]
            fields[field_name] = forms.MultipleChoiceField(choices=choices, **common_args)

        # Boolean (multi)
        if field_schema.get('type') == 'bool':
            fields[field_name] = forms.BooleanField(widget=forms.CheckboxInput(), **common_args)

        # Date field
        elif field_schema.get('type') == 'string' and field_schema.get('format') == 'date':
            validator_min = common_args.pop('min', None)
            validators_max = common_args.pop('max', None)
            attrs = {'type': 'date', 'class': 'form-control', 'min': validator_min, 'max': validators_max}
            attrs.update(common_args)
            fields[field_name] = forms.DateField(
                widget=forms.DateInput(attrs=attrs),
                **common_args
            )

        elif field_schema.get('type') == 'file':
            fields[field_name] = forms.FileField(
                widget=forms.FileInput(attrs={'type': 'file', 'class': 'custom-file-input'}),
                **common_args
            )

        elif field_schema.get('type') == 'geolocation':
            fields['get_geoloc'] = ButtonField(
                widget=ButtonWidget(
                    label=_('Use my location'),
                    attrs={"class": "btn btn-secondary btn-use-location"}
                ), **common_args
            )
            fields[field_name] = forms.CharField(
                widget=forms.HiddenInput(attrs={'class': 'coordinates'}),
                **common_args
            )

        else:
            field_type = field_schema.get('type', 'string')
            field_class = field_map.get(field_type, forms.CharField)
            fields[field_name] = field_class(**common_args)

    return type(f"DynamicFormPage{page_index}", (forms.Form,), fields)
