import datetime
from django.views.generic.edit import CreateView
from django.template.response import TemplateResponse
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from subprojects.models import Attachment
from trackableobjects.models import TrackableObject, TrackableObjectInstance
from administrativelevels.models import AdministrativeLevel, AdministrativeUnit
from src.permissions import IsFieldAgentUserMixin
from utils.json_form_parser import parse_custom_jsonschema, schema_requires_assigned_units
from django.contrib import messages


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


class TrackableObjectInstanceCreateView(IsFieldAgentUserMixin, CreateView):
    model = TrackableObjectInstance
    queryset = TrackableObject.objects.all()
    fields = '__all__'
    template_name = "trackable_objects/mobile/register_trackable_object_resp.html"

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests: instantiate a form instance with the passed
        POST variables and then check if it's valid.
        """
        self.object = self.get_object()
        if not self.has_object_permission_groups():
            return self.handle_no_permission()
        form = self.get_custom_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.has_object_permission_groups():
            return self.handle_no_permission()
        return self.render_to_response(self.get_context_data())

    def form_valid(self, form):
        cleaned_data = serialize_for_json(form.cleaned_data)

        for key in cleaned_data.keys():
            if key in form.files.keys():
                cleaned_data[key] = 'Attachment'

            if hasattr(cleaned_data[key], 'id') and hasattr(cleaned_data[key], '_meta'):
                cleaned_data[key] = cleaned_data[key].id

        instance = self.model(
            trackable_object=self.object,
            created_by=self.request.user,
            jsonForm=cleaned_data
        )
        instance.save()

        if form.files is not None:
            for key, value in form.files.items():
                Attachment.objects.create(
                    trackable_object_instance=instance,
                    field_name=key,
                    file=value,
                )

        messages.success(self.request, f"Successfully created {self.object.name} instance.")

        return HttpResponseRedirect(
            reverse_lazy(
                'trackableobjects:mobile:trackable_object_instance_registration_list',
                args=[self.object.id]
            )
        )

    def form_invalid(self, form):
        return TemplateResponse(self.request, self.template_name, {
            'form': form,
            'custom_form': self.get_custom_form(),
            'object': self.object,
            'trackable_object': self.object,
            'administrative_levels': AdministrativeLevel.objects.all().order_by('order'),
        })

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['custom_form'] = self.get_custom_form()
        context['trackable_object'] = self.object
        context['administrative_levels'] = AdministrativeLevel.objects.all().order_by('order')
        return context

    def get_custom_form(self):
        try:
            trackable_object = self.object
            schema_json = trackable_object.jsonForm if trackable_object else {
                "form": [
                    {
                        "page": {
                            "properties": {},
                            "required": []
                        }
                    }
                ]
            }
        except TrackableObject.DoesNotExist:
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

        admin_level_ids = []
        if schema_requires_assigned_units(schema_json):
            admin_level_ids = AdministrativeUnit.get_descendant_ids(
                self.request.user.administrative_units.values_list('id', flat=True)
            )

        form_class = parse_custom_jsonschema(
            schema_json, page_index=0,
            administrative_level_ids=admin_level_ids
        )

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

    def has_object_permission_groups(self):
        groups = self.object.groups.all()
        for group in groups:
            if not self.request.user.groups.filter(id=group.id).exists():
                return False
        return True
