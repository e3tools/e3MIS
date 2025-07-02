import json
from django.views.generic.edit import CreateView
from django.template.response import TemplateResponse
from subprojects.models import SubprojectCustomField, SubprojectFormResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from utils.json_form_parser import parse_custom_jsonschema


class CustomFormUpdateView(LoginRequiredMixin, CreateView):
    model = SubprojectFormResponse
    queryset = SubprojectCustomField.objects.all()
    fields = '__all__'
    template_name = "subprojects/mobile/custom_form_update_form.html"

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests: instantiate a form instance with the passed
        POST variables and then check if it's valid.
        """
        self.object = self.get_object()
        form = self.get_custom_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data())

    def form_valid(self, form):

        instance = self.model(
            custom_form=self.object,
            filled_by=self.request.user,
            subproject=self.object.subprojects.get(pk=self.kwargs['subproject']),
            response_schema=form.cleaned_data
        )
        instance.save()

        return TemplateResponse(self.request, "subprojects/partial_update_success.html", {
            'subproject': instance.subproject,
        })

    def form_invalid(self, form):
        return TemplateResponse(self.request, self.template_name, {
            'form': form,
            'custom_form': self.get_custom_form(),  # ensure custom form is re-included on error
            'object': self.object,
        })

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['custom_form'] = self.get_custom_form()
        return context

    def get_custom_form(self):
        try:
            custom_form_config = self.object
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

        return form_class(**self.get_form_kwargs())

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
        }

        if self.request.method in ("POST", "PUT"):
            kwargs.update(
                {
                    "data": self.request.POST,
                    "files": self.request.FILES,
                }
            )
        return kwargs

    def get_custom_field_names(self):
        try:
            custom_form_config = SubprojectCustomField.objects.last()
            schema_json = custom_form_config.config_schema if custom_form_config else {}
            return list(schema_json['form'][0]['page']['properties'].keys())
        except Exception:
            return []


omk = {
    "form": [
        {
            "page": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {
                        "type": "string"
                    },
                    "last_name": {
                        "type": "string"
                    }
                }
            },
            "options": {
                "fields": {
                    "name": {
                        "label": "What's your name",
                        "help": "This is your name"
                    },
                    "last_name": {
                        "label": "Your last name",
                        "help": "Here goes your lat name"
                    }
                }
            }
        }
    ]
}
