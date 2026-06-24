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


class CascadeAdminUnitSelect(forms.Select):
    """Render only the blank option plus the currently-selected one.

    For non-restricted ``administrative_level`` fields the cascading selects in
    ``dynamic_form_runtime.js`` hide this ``<select>`` and rebuild the choices
    from the API, so materializing the full AdministrativeUnit tree server-side
    is wasted work (and an N+1 over ``obj.level``). The field keeps its full
    queryset for validation; we only skip rendering the options here. The
    selected value is still emitted so the JS can read it (``$select.val()``) and
    preselect the cascade when editing an existing response.
    """

    def optgroups(self, name, value, attrs=None):
        options = [self.create_option(name, '', '', False, 0, attrs=attrs)]
        for index, option_value in enumerate(value):
            if option_value in ('', None):
                continue
            options.append(
                self.create_option(name, option_value, option_value, True, index + 1, attrs=attrs)
            )
        return [(None, options, 0)]


def schema_requires_assigned_units(schema_json, page_index=0):
    """True if any field on the page restricts choices to the user's assigned units.

    Lets the views skip the expensive descendant lookup entirely when no field
    needs it (the common case).
    """
    try:
        page_schema = schema_json['form'][page_index]['page']
    except (KeyError, IndexError, TypeError):
        return False
    for field_schema in page_schema.get('properties', {}).values():
        if field_schema.get('type') in ('administrative_level', 'trackable_object'):
            if field_schema.get('validators', {}).get('administrative_level_restriction') == 'true':
                return True
    return False


def parse_custom_jsonschema(schema_json, page_index=0, administrative_level_ids=[], parent_form_data=None):
    """
    Parse JSON schema and create Django form.

    Args:
        schema_json: The form schema
        page_index: Current page index
        administrative_level_ids: List of admin level IDs for filtering
        parent_form_data: Dictionary containing parent form responses for cross-form conditionals
                         Format: {'field_name': value, 'another_field': value, ...}
    """
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

        widget_attrs['placeholder'] = meta.get('placeholder', '')

        if dependencies:
            # NEW: Handle multiple conditions
            if 'conditions' in dependencies:
                conditions = dependencies['conditions']

                # Evaluate all conditions
                if parent_form_data:
                    results = []
                    for condition in conditions:
                        dep_field = condition.get('field')
                        is_parent_dependency = condition.get('is_parent_form', False)

                        if is_parent_dependency:
                            parent_value = parent_form_data.get(dep_field)
                            result = evaluate_condition(
                                parent_value,
                                condition.get('operator', 'equals'),
                                condition.get('value', '')
                            )
                            results.append(result)
                        else:
                            # For current form dependencies, we can't evaluate at render time
                            # Let JavaScript handle it
                            results.append(None)

                    # Evaluate combined logic
                    final_result = evaluate_multiple_conditions(conditions, results)

                    # If condition is not met, hide the field initially
                    if final_result is False:
                        widget_attrs['style'] = 'display: none;'
                        widget_attrs['data-initially-hidden'] = 'true'

                # Set data attributes for JavaScript evaluation
                widget_attrs['data-conditional'] = 'true'
                widget_attrs['data-conditions'] = json.dumps(conditions)

            else:
                # OLD: Single condition (backward compatibility)
                for dep_field, dep_config in dependencies.items():
                    is_parent_dependency = dep_config.get('is_parent_form', False)

                    widget_attrs['data-depends-on'] = dep_field
                    widget_attrs['data-depends-operator'] = dep_config.get('operator', 'equals')
                    widget_attrs['data-depends-value'] = dep_config.get('value', '')
                    widget_attrs['data-conditional'] = 'true'
                    widget_attrs['data-is-parent-form'] = 'true' if is_parent_dependency else 'false'

                    # If it's a parent form dependency and we have parent data, evaluate immediately
                    if is_parent_dependency and parent_form_data:
                        parent_value = parent_form_data.get(dep_field)
                        should_show = evaluate_condition(
                            parent_value,
                            dep_config.get('operator', 'equals'),
                            dep_config.get('value', '')
                        )

                        # If condition is not met, hide the field initially
                        if not should_show:
                            widget_attrs['style'] = 'display: none;'
                            widget_attrs['data-initially-hidden'] = 'true'

        field_instance = None

        # Dropdown (enum)
        if field_schema.get('type') == 'string' and 'enum' in field_schema:
            choices = [(opt, opt) for opt in field_schema['enum']]
            if field_schema.get('display') == 'radio':
                field_instance = forms.ChoiceField(
                    choices=choices,
                    widget=forms.RadioSelect(attrs=widget_attrs),
                    **common_args
                )
            else:
                widget_attrs['class'] = widget_attrs.get('class', '') + ' form-control'
                field_instance = forms.ChoiceField(
                    choices=choices,
                    widget=forms.Select(attrs=widget_attrs),
                    **common_args
                )

        # Multiselect (multi)
        elif field_schema.get('type') == 'string' and 'multi' in field_schema:
            choices = [(opt, opt) for opt in field_schema['multi']]
            if field_schema.get('display') == 'checkboxes':
                field_instance = forms.MultipleChoiceField(
                    choices=choices,
                    widget=forms.CheckboxSelectMultiple(attrs=widget_attrs),
                    **common_args
                )
            else:
                widget_attrs['class'] = widget_attrs.get('class', '') + ' form-control'
                field_instance = forms.MultipleChoiceField(
                    choices=choices,
                    widget=forms.SelectMultiple(attrs=widget_attrs),
                    **common_args
                )

        # TrackableObject
        elif field_schema.get('type') == 'trackable_object':
            administrative_level_restriction = validators.get('administrative_level_restriction', 'false')
            queryset = TrackableObjectInstance.objects.select_related('trackable_object').filter(
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
            max_admin_level_order = validators.get('max_admin_level_order', None)
            queryset = AdministrativeUnit.objects.select_related('level').all()
            if administrative_level_restriction == 'true':
                queryset = queryset.filter(id__in=administrative_level_ids)
            elif max_admin_level_order is not None:
                queryset = queryset.filter(level__order__lte=int(max_admin_level_order))
            widget_attrs['class'] = widget_attrs.get('class', '') + ' form-control'
            widget_attrs['data-field-type'] = 'administrative_level'
            widget_attrs['data-admin-level-restriction'] = administrative_level_restriction
            # Expose the max level so the cascading selects on mobile can limit depth.
            # Without this attribute the mobile JS defaults to 0 (no limit) and shows all levels.
            if administrative_level_restriction != 'true' and max_admin_level_order is not None:
                widget_attrs['data-max-level-order'] = int(max_admin_level_order)
            # When the field is restricted the server-rendered options are the ones
            # actually used (the JS keeps the native select). Otherwise the cascade JS
            # rebuilds the options from the API, so we avoid rendering the full tree.
            if administrative_level_restriction == 'true':
                widget = forms.Select(attrs=widget_attrs)
            else:
                widget = CascadeAdminUnitSelect(attrs=widget_attrs)
            field_instance = forms.ModelChoiceField(
                queryset=queryset,
                widget=widget,
                **common_args
            )
            field_instance.label_from_instance = lambda obj: "{} ({})".format(obj.name, obj.level.name)

        # Boolean
        elif field_schema.get('type') == 'bool':
            field_instance = forms.TypedChoiceField(
                choices=[('true', 'Yes'), ('false', 'No')],
                coerce=lambda x: x == 'true' if x != '' else None,
                empty_value=None,
                widget=forms.RadioSelect(attrs=widget_attrs),
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

            # Handle "today" as a dynamic value
            import datetime
            today_str = datetime.date.today().isoformat()

            if validator_min:
                if validator_min.lower() == 'today':
                    date_attrs['min'] = today_str
                else:
                    date_attrs['min'] = validator_min

            if validators_max:
                if validators_max.lower() == 'today':
                    date_attrs['max'] = today_str
                else:
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
            if field_type == 'number':
                number_attrs['step'] = 'any'
            else:  # integer
                number_attrs['step'] = '1'
                if 'min_value' not in validators:
                    number_attrs['min'] = 0
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

            if field_schema.get('display') == 'textarea':
                field_instance = forms.CharField(
                    widget=forms.Textarea(attrs=text_attrs),
                    **common_args
                )
            else:
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

    # Collect boolean field names for initial data normalization
    bool_field_names = {name for _, name, f in field_list if isinstance(f, forms.TypedChoiceField) and any(c[0] == 'true' for c in f.choices)}

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial')
        if initial and bool_field_names:
            for fname in bool_field_names:
                if fname in initial and isinstance(initial[fname], bool):
                    initial[fname] = 'true' if initial[fname] else 'false'
        forms.Form.__init__(self, *args, **kwargs)

    fields['__init__'] = __init__

    return type(f"DynamicFormPage{page_index}", (forms.Form,), fields)


def evaluate_multiple_conditions(conditions, results):
    """
    Evaluate multiple conditions with AND/OR logic.

    Args:
        conditions: List of condition objects with 'logic' property
        results: List of boolean results for each condition

    Returns:
        bool: Final result after applying all logic operators
    """
    if not conditions or not results:
        return True

    # Filter out None results (from current form conditions we can't evaluate)
    # If any result is None, we can't determine the final result server-side
    if None in results:
        return None

    # Start with first condition result
    final_result = results[0]

    # Apply each logic operator
    for i in range(len(conditions) - 1):
        logic = conditions[i].get('logic', 'AND')
        next_result = results[i + 1]

        if logic == 'AND':
            final_result = final_result and next_result
        elif logic == 'OR':
            final_result = final_result or next_result

    return final_result


def evaluate_condition(field_value, operator, expected_value):
    """
    Evaluate a conditional expression.

    Args:
        field_value: The actual value from the form
        operator: The comparison operator (equals, not_equals, contains, greater_than, less_than, between)
        expected_value: The expected value to compare against

    Returns:
        bool: True if condition is met, False otherwise
    """
    # Handle None/empty values
    if field_value is None or field_value == '':
        return False

    # Convert to string for comparison if needed
    field_value_str = str(field_value)
    expected_value_str = str(expected_value)

    if operator == 'equals':
        return field_value_str == expected_value_str

    elif operator == 'not_equals':
        return field_value_str != expected_value_str

    elif operator == 'contains':
        return expected_value_str in field_value_str

    elif operator == 'greater_than':
        try:
            return float(field_value) > float(expected_value)
        except (ValueError, TypeError):
            return False

    elif operator == 'less_than':
        try:
            return float(field_value) < float(expected_value)
        except (ValueError, TypeError):
            return False

    elif operator == 'between':
        # Expected format: "min,max"
        try:
            min_val, max_val = expected_value.split(',')
            field_val = float(field_value)
            return float(min_val) <= field_val <= float(max_val)
        except (ValueError, TypeError, AttributeError):
            return False

    return False
