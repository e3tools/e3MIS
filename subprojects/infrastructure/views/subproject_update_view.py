import json
from django.views.generic.edit import UpdateView
from django.template.response import TemplateResponse
from subprojects.models import Subproject, SubprojectCustomField
from subprojects.infrastructure.forms.subproject_update_form import SubprojectForm
from django.contrib.auth.mixins import LoginRequiredMixin
from src.permissions import IsStaffMemberMixin
from utils.json_form_parser import parse_custom_jsonschema


class SubprojectUpdateView(LoginRequiredMixin, IsStaffMemberMixin, UpdateView):
    model = Subproject
    form_class = SubprojectForm
    template_name = "subprojects/partial_update_form.html"

    def form_valid(self, form):
        # Bind and validate the custom form from POST data
        custom_form = self.get_custom_form(bind_from_post=True)

        if custom_form.is_valid():
            # Save main form and get updated object
            self.object = form.save()

            # Get custom field names from the schema to ensure only those are stored
            custom_field_names = self.get_custom_field_names()

            # Extract cleaned custom fields only
            custom_data = {
                key: value
                for key, value in custom_form.cleaned_data.items()
                if key in custom_field_names
            }

            self.object.custom_fields = json.dumps(custom_data)
            self.object.save()

            return TemplateResponse(self.request, "subprojects/partial_update_success.html", {
                'subproject': self.object,
            })
        else:
            return self.form_invalid(form)

    def form_invalid(self, form):
        print('here invalid')
        return TemplateResponse(self.request, self.template_name, {
            'form': form,
            'custom_form': self.get_custom_form(),  # ensure custom form is re-included on error
            'object': self.object,
        })

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['custom_form'] = self.get_custom_form()
        return context

    def get_custom_form(self, bind_from_post=False):
        try:
            custom_form_config = SubprojectCustomField.objects.last()
            schema_json = custom_form_config.config_schema if custom_form_config else {
                "form": [
                    {
                        "page": {
                            "properties": {},
                            "required": []
                        }
                    }
                ]
            }
        except SubprojectCustomField.DoesNotExist:
            schema_json = {
                "form": [
                    {
                        "page": {
                            "properties": {},
                            "required": []
                        }
                    }
                ]
            }

        form_class = parse_custom_jsonschema(schema_json, page_index=0)

        if bind_from_post and self.request.method in ["POST"]:
            return form_class(data=self.request.POST)

        if self.object and self.object.custom_fields:
            try:
                custom_fields = (
                    json.loads(self.object.custom_fields)
                    if isinstance(self.object.custom_fields, (str, bytes, bytearray))
                    else self.object.custom_fields
                )
                post_data = {k: str(v) for k, v in custom_fields.items()}
                return form_class(data=post_data)
            except (json.JSONDecodeError, AttributeError):
                pass

        return form_class()


    def get_custom_field_names(self):
        try:
            custom_form_config = SubprojectCustomField.objects.last()
            schema_json = custom_form_config.config_schema if custom_form_config else {}
            return list(schema_json['form'][0]['page']['properties'].keys())
        except Exception:
            return []