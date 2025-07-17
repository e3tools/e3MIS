import json
from django.views.generic.edit import CreateView
from django.template.response import TemplateResponse
from subprojects.models import SubprojectCustomField, SubprojectFormResponse, Subproject
from django.contrib.auth.mixins import LoginRequiredMixin
from utils.json_form_parser import parse_custom_jsonschema
import datetime

def serialize_for_json(data):
    """
    Recursively converts all datetime.date and datetime.datetime objects to ISO strings.
    """
    if isinstance(data, dict):
        return {k: serialize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [serialize_for_json(item) for item in data]
    elif isinstance(data, (datetime.date, datetime.datetime)):
        return data.isoformat()
    return data


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
        self.project = Subproject.objects.get(pk=self.kwargs['subproject'])
        form = self.get_custom_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.project = Subproject.objects.get(pk=self.kwargs['subproject'])
        return self.render_to_response(self.get_context_data())

    def form_valid(self, form):
        subproject = Subproject.objects.get(pk=self.kwargs['subproject'])
        instance = self.model.objects.filter(custom_form=self.object, subproject=subproject).first()
        cleaned_data = serialize_for_json(form.cleaned_data)

        if instance is None:
            instance = self.model(
                custom_form=self.object,
                filled_by=self.request.user,
                subproject=subproject,
                response_schema=cleaned_data
            )
        else:
            instance.filled_by = self.request.user
            instance.response_schema = cleaned_data
        instance.save()

        return TemplateResponse(self.request, "subprojects/mobile/custom_form_update_form.html", {
            'subproject': subproject,
            'custom_form': self.get_custom_form(),
            'success': True,  # <<<<<<<<<<<<<<<<
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
        context['subproject'] = self.project
        return context

    def get_initial(self):
        """Return the initial data to use for forms on this view."""
        form_response = SubprojectFormResponse.objects.filter(subproject=self.project, custom_form=self.object).first()
        if form_response is not None:
            return form_response.response_schema
        return self.initial.copy()

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
