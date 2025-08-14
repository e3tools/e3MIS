import datetime
from django.views.generic.edit import CreateView
from django.template.response import TemplateResponse
from subprojects.models import Attachment
from trackableobjects.models import TrackableObject, TrackableObjectResponse
from src.permissions import IsFieldAgentUserMixin
from utils.json_form_parser import parse_custom_jsonschema


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


class TrackableObjectResponseCreateView(IsFieldAgentUserMixin, CreateView):
    model = TrackableObjectResponse
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
        instance = self.model.objects.filter(trackable_object=self.object).first()
        cleaned_data = serialize_for_json(form.cleaned_data)

        for key in cleaned_data.keys():
            if key in form.files.keys():
                cleaned_data[key] = 'Attachment'

        if instance is None:
            instance = self.model(
                trackable_object=self.object,
                created_by=self.request.user,
                jsonForm=cleaned_data
            )
        else:
            instance.filled_by = self.request.user
            instance.response_schema = cleaned_data
        instance.save()

        # if form.files is not None:
        #     for key, value in form.files.items():
        #         Attachment.objects.create(
        #             subproject_form_response=instance,
        #             field_name=key,
        #             file=value,
        #         )

        return TemplateResponse(self.request, "trackable_objects/mobile/register_trackable_object_resp.html", {
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
        return context

    def get_initial(self):
        """Return the initial data to use for forms on this view."""
        trackable_object_response = TrackableObjectResponse.objects.filter(trackable_object=self.object).first()
        if trackable_object_response is not None:
            initial = trackable_object_response.jsonForm
            # attachment_initial = Attachment.objects.filter(subproject_form_response=form_response).all()
            # for attachment in attachment_initial:
            #     initial.update({attachment.field_name: attachment.file})
            return initial
        return self.initial.copy()

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
            trackable_object = TrackableObject.objects.last()
            schema_json = trackable_object.jsonForm if trackable_object else {}
            return list(schema_json['form'][0]['page']['properties'].keys())
        except Exception:
            return []

    def has_object_permission_groups(self):
        groups = self.object.groups.all()
        for group in groups:
            if not self.request.user.groups.filter(id=group.id).exists():
                return False
        return True
