from django import forms

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

        # Dropdown (enum)
        if field_schema.get('type') == 'string' and 'enum' in field_schema:
            choices = [(opt, opt) for opt in field_schema['enum']]
            fields[field_name] = forms.ChoiceField(choices=choices, **common_args)

        # Date field
        elif field_schema.get('type') == 'string' and field_schema.get('format') == 'date':
            fields[field_name] = forms.DateField(
                widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
                **common_args
            )

        elif field_schema.get('type') == 'file':
            fields[field_name] = forms.FileField(
                widget=forms.FileInput(attrs={'type': 'file', 'class': 'custom-file-input'}),
                **common_args
            )
        else:
            field_type = field_schema.get('type', 'string')
            field_class = field_map.get(field_type, forms.CharField)
            fields[field_name] = field_class(**common_args)

    return type(f"DynamicFormPage{page_index}", (forms.Form,), fields)