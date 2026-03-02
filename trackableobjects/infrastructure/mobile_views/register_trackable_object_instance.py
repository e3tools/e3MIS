import datetime
from django.views.generic.edit import CreateView
from django.template.response import TemplateResponse
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from subprojects.models import Attachment
from trackableobjects.models import TrackableObject, TrackableObjectInstance
from src.permissions import IsFieldAgentUserMixin
from utils.json_form_parser import parse_custom_jsonschema
from django.contrib import messages

from administrativelevels.models import AdministrativeUnit


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
        post_dict = self.request.POST.copy()

        cleaned_data = serialize_for_json(form.cleaned_data)

        for key in cleaned_data.keys():
            if key in form.files.keys():
                cleaned_data[key] = 'Attachment'

            if isinstance(cleaned_data[key], TrackableObjectInstance) or isinstance(cleaned_data[key], AdministrativeUnit):
                cleaned_data[key] = cleaned_data[key].id

        instance = self.model(
            trackable_object=self.object,
            created_by=self.request.user,
            jsonForm=cleaned_data
        )
        instance.save()
        instance.administrative_units.add(*post_dict.pop('administrative_units'))

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
            'custom_form': self.get_custom_form(),  # ensure custom form is re-included on error
            'object': self.object,
        })

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['custom_form'] = self.get_custom_form()
        administrative_units_qs = AdministrativeUnit.objects.filter(
            id__in=[id for unit in self.request.user.administrative_units.all() for id in self.get_descendants(unit)]).select_related('parent')

        response_list = list()
        for administrative_unit in administrative_units_qs:
            flag = False
            for node in response_list:
                if 'parent_id' in node and node['parent_id'] == administrative_unit.parent.id:
                    node['children'].append({'id': administrative_unit.id, 'name': administrative_unit.hierarchy_name})
                    flag = True
            if not flag:
                response_list.append({
                    'parent_id': administrative_unit.parent.id,
                    'name': administrative_unit.parent.name,
                    'children': [{'id': administrative_unit.id, 'name': administrative_unit.hierarchy_name}]
                })

        context['administrative_units'] = response_list
        context['trackable_object'] = self.object

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

        form_class = parse_custom_jsonschema(
            schema_json, page_index=0,
            administrative_level_ids=[id for unit in self.request.user.administrative_units.all() for id in self.get_descendants(unit)]
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

    def get_descendants(self, administrative_unit):
        descendants = list()

        def recurse(node):
            if node.children.exists():
                for child in node.children.all():
                    recurse(child)
            else:
                descendants.append(node.id)

        recurse(administrative_unit)
        return descendants
